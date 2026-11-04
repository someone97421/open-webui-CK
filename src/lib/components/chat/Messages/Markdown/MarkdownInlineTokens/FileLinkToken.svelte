<script lang="ts">
	import { v4 as uuidv4 } from 'uuid';
	import { getContext, onDestroy } from 'svelte';
	import { readable, type Readable } from 'svelte/store';
	import { toast } from 'svelte-sonner';
	import { settings, terminalServers, user } from '$lib/stores';
	import { WEBUI_API_BASE_URL } from '$lib/constants';
	import { getFileById, uploadFile } from '$lib/apis/files';
	import { joinTerminalPath, resolveTerminalConnection, terminalRequest } from '$lib/apis/terminal';
	import { createPyodideWorker, getPyodideScope } from '$lib/pyodide/createPyodideWorker';
	import { fileContentType, type ChatFileReference } from '$lib/utils/chatFiles';
	import { copyToClipboard } from '$lib/utils';
	import Modal from '$lib/components/common/Modal.svelte';
	import ToolOutputFile from '../../ToolOutputFile.svelte';

	export let reference: ChatFileReference;
	export let chatId: string;
	export let text: string;
	const chatMode = getContext<Readable<any> | undefined>('chatMode') ?? readable(null);
	let show = false;
	let loading = false;
	let publishing = false;
	let item: any = null;
	let blob: Blob | null = null;
	let targetChatId = '';
	let copiedUrl = '';
	let disposed = false;
	let cancelRead: (() => void) | undefined;

	function readLocalFile(path: string, id: string): Promise<Blob> {
		const scope = getPyodideScope(id);
		const worker = createPyodideWorker(scope, { background: true });
		const requestId = `link-${uuidv4()}`;
		return new Promise((resolve, reject) => {
			const finish = () => {
				worker.removeEventListener('message', handler);
				worker.terminate();
				cancelRead = undefined;
			};
			const handler = (event: MessageEvent) => {
				if (event.data?.id !== requestId) return;
				finish();
				if (event.data.error || !event.data.data) reject(new Error('文件不存在或当前浏览器没有保存该文件'));
				else resolve(new Blob([event.data.data], { type: fileContentType(path) }));
			};
			cancelRead = () => { finish(); reject(new Error('文件读取已取消')); };
			worker.addEventListener('message', handler);
			worker.postMessage({ id: requestId, type: 'fs:read', path });
		});
	}

	async function openFile() {
		if (loading) return;
		const ref = reference;
		const owner = $user?.id;
		const originalChatId = chatId;
		const signature = JSON.stringify(ref);
		const current = () => !disposed && $user?.id === owner && chatId === originalChatId && JSON.stringify(reference) === signature;
		loading = true;
		blob = null;
		item = null;
		copiedUrl = '';
		targetChatId = ref.kind === 'workspace' ? ref.chatId || chatId : chatId;
		try {
			if (!targetChatId) throw new Error('请先打开文件所属的聊天');
			if (ref.kind === 'stored') {
				const file = await getFileById(localStorage.token, ref.fileId);
				if (!file) throw new Error('文件不存在或无权访问');
				item = { source: 'open_webui', path: `/api/v1/files/${ref.fileId}/content`, name: file.meta?.name || file.filename, content_type: file.meta?.content_type };
				copiedUrl = new URL(`${WEBUI_API_BASE_URL}/files/${ref.fileId}/content`, window.location.origin).href;
			} else {
				if ($chatMode && !$chatMode.ready) throw new Error('聊天工作区仍在加载，请稍后重试');
				const selector = ref.terminalId || $chatMode?.project?.terminal_id;
				if (selector) {
					const connection = resolveTerminalConnection(selector, $terminalServers ?? [], $settings?.terminalServers ?? [], localStorage.token);
					if (!connection) throw new Error('文件所属的 Terminal 不可用');
					let path = ref.path;
					if (!path.startsWith('/')) {
						const cwd = await terminalRequest<{ cwd: string }>(connection, targetChatId, '/files/cwd');
						path = joinTerminalPath(cwd.cwd, path);
					}
					item = { source: 'open_terminal', path, terminal_selector: selector };
					if (connection.system) copiedUrl = new URL(`${connection.baseUrl}/chats/${encodeURIComponent(targetChatId)}/files/view?path=${encodeURIComponent(path)}`, window.location.origin).href;
				} else {
					const path = ref.path.startsWith('/') ? ref.path : `/mnt/uploads/${ref.path}`;
					blob = await readLocalFile(path, targetChatId);
					item = { source: 'pyodide', path, name: path.split('/').pop() || 'file' };
				}
			}
			if (current()) show = true;
		} catch (error) {
			if (current()) toast.error(error instanceof Error ? error.message : String(error));
		} finally {
			if (!disposed) loading = false;
		}
	}

	async function copyLink() {
		if (publishing) return;
		const owner = $user?.id;
		const originalItem = item;
		const originalChatId = chatId;
		const current = () => !disposed && $user?.id === owner && chatId === originalChatId && item === originalItem;
		publishing = true;
		try {
			if (!copiedUrl && blob) {
				const file = await uploadFile(localStorage.token, new File([blob], item.name, { type: blob.type }), { chat_id: targetChatId }, false, false);
				if (!file?.id) throw new Error('文件保存失败');
				if (!current()) return;
				copiedUrl = new URL(`${WEBUI_API_BASE_URL}/files/${file.id}/content`, window.location.origin).href;
			}
			if (!copiedUrl) throw new Error('此连接无法提供可复制的 WebUI 文件链接');
			if (!await copyToClipboard(copiedUrl)) throw new Error('复制失败，请检查剪贴板权限');
			if (current()) toast.success('文件链接已复制');
		} catch (error) {
			if (current()) toast.error(error instanceof Error ? error.message : String(error));
		} finally {
			if (!disposed) publishing = false;
		}
	}

	$: if (!show && !loading) { blob = null; item = null; }

	onDestroy(() => { disposed = true; cancelRead?.(); });
</script>

<button type="button" class="inline text-left underline decoration-current underline-offset-2 disabled:opacity-50" disabled={loading} title={loading ? '正在打开文件…' : '预览或下载文件'} on:click|stopPropagation={openFile}>{text}</button>
<Modal bind:show size="xl" ariaLabel="文件预览">
	<div class="p-4">
		<div class="mb-2 flex items-center justify-end gap-3 text-xs">
			{#if copiedUrl || blob}<button type="button" class="underline disabled:opacity-50" disabled={publishing} on:click={copyLink} title={blob && !copiedUrl ? '上传到文件库，其他设备登录当前账号后可访问' : '需要登录并拥有文件访问权限'}>{publishing ? '正在保存…' : blob && !copiedUrl ? '保存到文件库并复制链接' : '复制链接'}</button>{/if}
			<button type="button" on:click={() => (show = false)} aria-label="关闭文件预览">关闭</button>
		</div>
		{#if show && item}<ToolOutputFile {item} chatId={targetChatId} localBlob={blob} />{/if}
	</div>
</Modal>
