<script lang="ts">
	import { v4 as uuidv4 } from 'uuid';
	import { getContext, onMount, onDestroy, tick } from 'svelte';
	import {
		createPyodideWorker,
		getPyodideScope,
		type PyodideScope
	} from '$lib/pyodide/createPyodideWorker';
	import type { FileEntry } from '$lib/apis/terminal';

	import FileNavToolbar from './FileNav/FileNavToolbar.svelte';
	import FileEntryRow from './FileNav/FileEntryRow.svelte';
	import FilePreview from './FileNav/FilePreview.svelte';
	import ConfirmDialog from '../common/ConfirmDialog.svelte';
	import Spinner from '../common/Spinner.svelte';
	import Folder from '../icons/Folder.svelte';
	import Document from '../icons/Document.svelte';

	const i18n = getContext('i18n');
	export let overlay = false;

	type Context = { scope: PyodideScope; generation: number; path: string };
	type NavEntry = { path: string; file: string | null };
	let activeScope: PyodideScope | null = null;
	let scopeGeneration = 0;
	let viewGeneration = 0;
	let disposed = false;
	const pendingRequests = new Set<() => void>();

	let currentPath = '/mnt/uploads';
	let entries: FileEntry[] = [];
	let loading = false;
	let error: string | null = null;
	let selectedFile: string | null = null;
	let fileLoading = false;
	let fileContent: string | null = null;
	let fileImageUrl: string | null = null;
	let isDragOver = false;
	let showDeleteConfirm = false;
	let deletePath = '';
	let deleteName = '';
	let deleteContext: Context | null = null;
	let creatingFolder = false;
	let newFolderName = '';
	let newFolderInput: HTMLInputElement;
	let creatingFile = false;
	let newFileName = '';
	let newFileInput: HTMLInputElement;
	let navHistory: NavEntry[] = [];
	let navIndex = -1;

	$: canGoBack = navIndex > 0;
	$: canGoForward = navIndex < navHistory.length - 1;

	const IMAGE_EXTS = new Set(['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'ico', 'avif']);
	const isImage = (path: string) => IMAGE_EXTS.has(path.split('.').pop()?.toLowerCase() ?? '');

	const isCurrent = (context: Context) => {
		if (disposed || context.generation !== scopeGeneration || activeScope !== context.scope) return false;
		const scope = getPyodideScope();
		return !!scope.userId && scope.key === context.scope.key && scope.generation === context.scope.generation;
	};
	const captureContext = (): Context | null => {
		if (!activeScope) return null;
		const context = { scope: activeScope, generation: scopeGeneration, path: currentPath };
		return isCurrent(context) ? context : null;
	};
	const isCurrentView = (context: Context, generation: number) =>
		isCurrent(context) && generation === viewGeneration;

	function sendWorkerMessage(msg: any, context: Context): Promise<any> {
		if (!isCurrent(context)) return Promise.reject(new Error('Python context changed'));
		const worker = createPyodideWorker(context.scope);
		const id = `fs-${uuidv4()}`;
		return new Promise((resolve, reject) => {
			let settled = false;
			const cleanup = () => {
				pendingRequests.delete(cancel);
				worker.removeEventListener('message', handler);
				worker.terminate();
			};
			const fail = (reason: unknown) => {
				if (settled) return;
				settled = true;
				cleanup();
				reject(reason instanceof Error ? reason : new Error(String(reason)));
			};
			const cancel = () => fail('Python context changed');
			const handler = (event: MessageEvent) => {
				if (event.data?.id !== id || settled) return;
				if (!isCurrent(context)) return cancel();
				if (event.data.error || event.data.success === false) {
					return fail(event.data.error || event.data.stderr || 'Python filesystem error');
				}
				settled = true;
				cleanup();
				resolve(event.data);
			};
			pendingRequests.add(cancel);
			worker.addEventListener('message', handler);
			try {
				worker.postMessage({ ...msg, id });
			} catch (error) {
				fail(error);
			}
		});
	}

	const pushNavHistory = (path: string, file: string | null = null) => {
		const current = navHistory[navIndex];
		if (current && current.path === path && current.file === file) return;
		navHistory = [...navHistory.slice(0, navIndex + 1), { path, file }];
		navIndex = navHistory.length - 1;
	};
	const navigateHistory = async (offset: number) => {
		const context = captureContext();
		const entry = navHistory[navIndex + offset];
		if (!context || !entry) return;
		navIndex += offset;
		const generation = await loadDir(entry.path, false);
		if (generation === null || !isCurrentView(context, generation) || !entry.file) return;
		await openEntry({ name: entry.file.split('/').pop() ?? '', type: 'file', size: 0 }, false);
	};
	const goBack = () => navigateHistory(-1);
	const goForward = () => navigateHistory(1);

	const buildBreadcrumbs = (path: string) => {
		const parts = path.split('/').filter(Boolean);
		return parts.reduce(
			(acc, part) => {
				const prev = acc[acc.length - 1];
				acc.push({ label: part, path: `${prev.path}${part}/` });
				return acc;
			},
			[{ label: '/', path: '/' }]
		);
	};
	$: breadcrumbs = buildBreadcrumbs(currentPath);

	const clearPreview = () => {
		fileContent = null;
		if (fileImageUrl) URL.revokeObjectURL(fileImageUrl);
		fileImageUrl = null;
	};

	const loadDir = async (path: string, rememberHistory = true): Promise<number | null> => {
		const context = captureContext();
		if (!context) return null;
		const generation = ++viewGeneration;
		loading = true;
		fileLoading = false;
		error = null;
		entries = [];
		selectedFile = null;
		clearPreview();
		currentPath = path.endsWith('/') ? path : path + '/';
		if (rememberHistory) pushNavHistory(currentPath);
		try {
			const res = await sendWorkerMessage({
				type: 'fs:list', path: currentPath.replace(/\/$/, '') || '/'
			}, context);
			if (!isCurrentView(context, generation)) return null;
			entries = (res.entries || []).sort((a: FileEntry, b: FileEntry) => {
				if (a.type !== b.type) return a.type === 'directory' ? -1 : 1;
				return a.name.localeCompare(b.name);
			});
			return generation;
		} catch {
			if (isCurrentView(context, generation)) {
				error = 'Failed to list directory';
				entries = [];
			}
			return null;
		} finally {
			if (isCurrentView(context, generation)) loading = false;
		}
	};

	const openEntry = async (entry: FileEntry, rememberHistory = true) => {
		const context = captureContext();
		if (!context) return;
		if (entry.type === 'directory') {
			await loadDir(`${context.path}${entry.name}/`, rememberHistory);
			return;
		}
		const generation = ++viewGeneration;
		const filePath = `${context.path}${entry.name}`;
		if (rememberHistory) pushNavHistory(context.path, filePath);
		selectedFile = filePath;
		loading = false;
		fileLoading = true;
		clearPreview();
		try {
			const res = await sendWorkerMessage({ type: 'fs:read', path: filePath }, context);
			if (!isCurrentView(context, generation)) return;
			if (isImage(filePath)) {
				fileImageUrl = URL.createObjectURL(new Blob([res.data]));
			} else {
				try {
					fileContent = new TextDecoder('utf-8', { fatal: true }).decode(res.data);
				} catch {
					fileContent = `[Binary file: ${entry.size ?? 0} bytes]`;
				}
			}
		} catch {
			if (isCurrentView(context, generation)) fileContent = 'Failed to read file';
		} finally {
			if (isCurrentView(context, generation)) fileLoading = false;
		}
	};

	const downloadFile = async (path: string) => {
		const context = captureContext();
		if (!context) return;
		try {
			const res = await sendWorkerMessage({ type: 'fs:read', path }, context);
			if (!isCurrent(context) || !res.data) return;
			const url = URL.createObjectURL(new Blob([res.data]));
			const a = document.createElement('a');
			a.href = url;
			a.download = path.split('/').pop() ?? 'file';
			a.click();
			URL.revokeObjectURL(url);
		} catch (error) {
			if (isCurrent(context)) console.error('Download failed:', error);
		}
	};

	const confirmDelete = (path: string, name: string) => {
		deleteContext = captureContext();
		if (!deleteContext) return;
		deletePath = path;
		deleteName = name;
		showDeleteConfirm = true;
	};
	const doDelete = async () => {
		const context = deleteContext;
		const path = deletePath;
		const generation = viewGeneration;
		if (!context || !isCurrent(context)) return;
		try {
			await sendWorkerMessage({ type: 'fs:delete', path }, context);
			if (isCurrentView(context, generation) && currentPath === context.path) await loadDir(context.path);
		} catch (error) {
			if (isCurrent(context)) console.error('Delete failed:', error);
		}
	};

	const startNewFolder = async () => {
		const context = captureContext();
		const generation = viewGeneration;
		if (!context) return;
		creatingFolder = true;
		newFolderName = '';
		await tick();
		if (isCurrentView(context, generation) && creatingFolder) newFolderInput?.focus();
	};
	const submitNewFolder = async () => {
		const context = captureContext();
		const generation = viewGeneration;
		const name = newFolderName.trim();
		creatingFolder = false;
		newFolderName = '';
		if (!context || !name) return;
		const path = `${context.path}${name}`.replace(/\/$/, '');
		try {
			await sendWorkerMessage({ type: 'fs:mkdir', path }, context);
			if (isCurrentView(context, generation)) await loadDir(context.path);
		} catch (error) {
			if (isCurrent(context)) console.error('Failed to create folder:', error);
		}
	};

	const startNewFile = async () => {
		const context = captureContext();
		const generation = viewGeneration;
		if (!context) return;
		creatingFile = true;
		newFileName = '';
		await tick();
		if (isCurrentView(context, generation) && creatingFile) newFileInput?.focus();
	};
	const submitNewFile = async () => {
		const context = captureContext();
		const generation = viewGeneration;
		const name = newFileName.trim();
		creatingFile = false;
		newFileName = '';
		if (!context || !name) return;
		try {
			await sendWorkerMessage({
				type: 'fs:upload', files: [{ name, data: new ArrayBuffer(0) }],
				dir: context.path.replace(/\/$/, '') || '/'
			}, context);
			if (isCurrentView(context, generation)) await loadDir(context.path);
		} catch (error) {
			if (isCurrent(context)) console.error('Failed to create file:', error);
		}
	};

	const uploadFiles = async (fileList: File[]) => {
		const context = captureContext();
		const generation = viewGeneration;
		if (!context) return;
		try {
			const payloads: { name: string; data: ArrayBuffer }[] = [];
			for (const file of fileList) {
				const data = await file.arrayBuffer();
				if (!isCurrent(context)) return;
				payloads.push({ name: file.name, data });
			}
			await sendWorkerMessage({
				type: 'fs:upload', files: payloads, dir: context.path.replace(/\/$/, '') || '/'
			}, context);
			if (isCurrentView(context, generation)) await loadDir(context.path);
		} catch (error) {
			if (isCurrent(context)) console.error('Upload failed:', error);
		}
	};

	const handleDragOver = (e: DragEvent) => {
		if (selectedFile || !captureContext() || !e.dataTransfer?.types.includes('Files')) return;
		e.preventDefault();
		e.stopPropagation();
		isDragOver = true;
	};
	const handleDrop = async (e: DragEvent) => {
		e.preventDefault();
		e.stopPropagation();
		isDragOver = false;
		if (selectedFile) return;
		const droppedFiles = Array.from(e.dataTransfer?.files ?? []);
		if (droppedFiles.length) await uploadFiles(droppedFiles);
	};

	const refreshView = async (preserveFile = false) => {
		const context = captureContext();
		const generation = viewGeneration;
		const file = selectedFile;
		if (!context) return;
		try {
			await sendWorkerMessage({ type: 'fs:sync' }, context);
			if (!isCurrentView(context, generation)) return;
			if (preserveFile && file) {
				await openEntry({ name: file.split('/').pop() ?? '', type: 'file', size: 0 });
			} else {
				await loadDir(context.path);
			}
		} catch (error) {
			if (isCurrentView(context, generation)) console.error('Refresh failed:', error);
		}
	};
	const onFilesChanged = () => void refreshView();
	const onScopeChanged = () => {
		if (disposed) return;
		const scope = getPyodideScope();
		if (activeScope?.key === scope.key && activeScope.generation === scope.generation) return;
		++scopeGeneration;
		++viewGeneration;
		activeScope = scope;
		for (const cancel of [...pendingRequests]) cancel();
		clearPreview();
		currentPath = '/mnt/uploads';
		entries = [];
		selectedFile = null;
		loading = false;
		fileLoading = false;
		error = null;
		isDragOver = false;
		showDeleteConfirm = false;
		deletePath = '';
		deleteName = '';
		deleteContext = null;
		creatingFolder = false;
		newFolderName = '';
		creatingFile = false;
		newFileName = '';
		navHistory = [];
		navIndex = -1;
		if (scope.userId) void loadDir(currentPath);
	};

	onMount(() => {
		window.addEventListener('pyodide:scope', onScopeChanged);
		window.addEventListener('pyodide:files', onFilesChanged);
		onScopeChanged();
	});
	onDestroy(() => {
		disposed = true;
		++scopeGeneration;
		++viewGeneration;
		for (const cancel of [...pendingRequests]) cancel();
		clearPreview();
		window.removeEventListener('pyodide:scope', onScopeChanged);
		window.removeEventListener('pyodide:files', onFilesChanged);
	});
</script>

<ConfirmDialog
	bind:show={showDeleteConfirm}
	title={$i18n.t('Delete {{name}}', { name: deleteName })}
	message={$i18n.t('Are you sure you want to delete this?')}
	on:confirm={doDelete}
/>

<div
	class="flex flex-col h-full min-h-0 min-w-0 relative"
	on:dragover={handleDragOver}
	on:dragleave={() => (isDragOver = false)}
	on:drop={handleDrop}
	role="region"
	aria-label={$i18n.t('Pyodide file browser')}
>
	{#if isDragOver}
		<div
			class="absolute inset-0 z-10 flex flex-col items-center justify-center bg-white/80 dark:bg-gray-850/80 backdrop-blur-sm pointer-events-none gap-1.5"
		>
			<svg
				xmlns="http://www.w3.org/2000/svg"
				viewBox="0 0 24 24"
				fill="none"
				stroke="currentColor"
				stroke-width="1.5"
				class="size-5 text-gray-400 dark:text-gray-500"
			>
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5m-13.5-9L12 3m0 0 4.5 4.5M12 3v13.5"
				/>
			</svg>
			<span class="text-xs text-gray-400 dark:text-gray-500">{$i18n.t('Drop files here')}</span>
		</div>
	{/if}

	{#if overlay}
		<div class="absolute inset-0 z-10 pointer-events-none" />
	{/if}

	<!-- Toolbar (shared with FileNav) -->
	<FileNavToolbar
		{breadcrumbs}
		{selectedFile}
		{loading}
		{canGoBack}
		{canGoForward}
		onGoBack={goBack}
		onGoForward={goForward}
		onNavigate={(path) => loadDir(path)}
		onRefresh={() => refreshView(true)}
		onNewFolder={startNewFolder}
		onNewFile={startNewFile}
		onUploadFiles={uploadFiles}
		onMove={() => {}}
	>
		<!-- File action buttons when a file is selected (slot content) -->
		<button
			class="shrink-0 p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-800 transition text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-400"
			on:click={() => selectedFile && downloadFile(selectedFile)}
			aria-label={$i18n.t('Download')}
		>
			<svg
				xmlns="http://www.w3.org/2000/svg"
				viewBox="0 0 20 20"
				fill="currentColor"
				class="size-3.5"
			>
				<path
					d="M10.75 2.75a.75.75 0 0 0-1.5 0v8.614L6.295 8.235a.75.75 0 1 0-1.09 1.03l4.25 4.5a.75.75 0 0 0 1.09 0l4.25-4.5a.75.75 0 0 0-1.09-1.03l-2.955 3.129V2.75Z"
				/>
				<path
					d="M3.5 12.75a.75.75 0 0 0-1.5 0v2.5A2.75 2.75 0 0 0 4.75 18h10.5A2.75 2.75 0 0 0 18 15.25v-2.5a.75.75 0 0 0-1.5 0v2.5c0 .69-.56 1.25-1.25 1.25H4.75c-.69 0-1.25-.56-1.25-1.25v-2.5Z"
				/>
			</svg>
		</button>
	</FileNavToolbar>

	<!-- Content area -->
	<div class="flex-1 min-h-0 flex flex-col">
		{#if selectedFile}
			<FilePreview {selectedFile} {fileLoading} {fileImageUrl} {fileContent} {overlay} />
		{:else if loading}
			<div class="flex items-center justify-center flex-1 p-6">
				<Spinner className="size-4" />
			</div>
		{:else if error}
			<div class="flex items-center justify-center flex-1 p-6">
				<div class="text-xs text-gray-500 dark:text-gray-400">{error}</div>
			</div>
		{:else if entries.length === 0 && !creatingFolder && !creatingFile}
			<div class="flex flex-col items-center justify-center flex-1 p-6 text-center gap-2">
				<Folder className="size-5 text-gray-300 dark:text-gray-600" />
				<div class="text-xs text-gray-400 dark:text-gray-500">
					{$i18n.t('No files yet. Upload files or run Python code to create them.')}
				</div>
			</div>
		{/if}

		{#if !loading && !error && !selectedFile}
			{#if creatingFolder}
				<div class="flex items-center gap-2 px-3 py-1.5">
					<Folder className="size-4 shrink-0 text-blue-400 dark:text-blue-300" />
					<input
						bind:this={newFolderInput}
						bind:value={newFolderName}
						class="min-w-0 flex-1 bg-transparent py-0.5 text-xs outline-hidden"
						placeholder={$i18n.t('Folder name')}
						on:keydown={(e) => {
							if (e.key === 'Enter') submitNewFolder();
							if (e.key === 'Escape') {
								creatingFolder = false;
								newFolderName = '';
							}
						}}
						on:blur={submitNewFolder}
					/>
				</div>
			{/if}
			{#if creatingFile}
				<div class="flex items-center gap-2 px-3 py-1.5">
					<Document className="size-4 shrink-0 text-gray-400 dark:text-gray-500" />
					<input
						bind:this={newFileInput}
						bind:value={newFileName}
						class="min-w-0 flex-1 bg-transparent py-0.5 text-xs outline-hidden"
						placeholder={$i18n.t('File name')}
						on:keydown={(e) => {
							if (e.key === 'Enter') submitNewFile();
							if (e.key === 'Escape') {
								creatingFile = false;
								newFileName = '';
							}
						}}
						on:blur={submitNewFile}
					/>
				</div>
			{/if}

			{#if entries.length > 0 || creatingFolder || creatingFile}
				<ul class="overflow-y-auto flex-1 min-h-0">
					{#each entries as entry (entry.name)}
						<FileEntryRow
							{entry}
							{currentPath}
							onOpen={openEntry}
							onDownload={downloadFile}
							onDelete={confirmDelete}
						/>
					{/each}
				</ul>
			{/if}
		{/if}
	</div>
</div>
