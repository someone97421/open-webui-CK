<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { goto } from '$app/navigation';
	import { toast } from 'svelte-sonner';
	import { user } from '$lib/stores';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import ConfirmDialog from '$lib/components/common/ConfirmDialog.svelte';
	import Switch from '$lib/components/common/Switch.svelte';
	import SkillImport from './SkillImport.svelte';
	import {
		listSkillPackages, getSkillPackage, updateSkillPackage, deleteSkillPackage,
		exportSkillPackage, downloadSkillBlob, skillPackageCreateUrl, skillPackageEditUrl,
		skillError, type SkillPackageContext
	} from '$lib/apis/skills';

	export let context: SkillPackageContext;
	let items: any[] = [];
	let loading = true;
	let unavailable = '';
	let query = '';
	let pending = '';
	let deleting: any = null;
	let showDelete = false;
	let showImport = false;
	let importFiles: File[] = [];
	let importInput: HTMLInputElement;
	let folderInput: HTMLInputElement;
	let controller: AbortController;
	$: canCreate = $user?.role === 'admin' || $user?.permissions?.workspace?.skills;
	$: canImport = $user?.role === 'admin' || $user?.permissions?.workspace?.skills_import;
	$: canExport = $user?.role === 'admin' || $user?.permissions?.workspace?.skills_export;
	$: visibleItems = items.filter((item) => `${item.name} ${item.description ?? ''} ${item.location ?? ''}`.toLowerCase().includes(query.toLowerCase()));
	const load = async () => {
		controller?.abort();
		controller = new AbortController();
		const signal = controller.signal;
		loading = true;
		unavailable = '';
		try {
			if (!context.terminal_id && !context.project_id) { unavailable = '请选择可用 Terminal'; items = []; return; }
			const result = await listSkillPackages(localStorage.token, context, '', signal);
			if (signal.aborted) return;
			items = result.items.filter((item: any) => item.source === 'terminal');
			const failures = (result.statuses ?? []).filter((status: any) => status.available === false);
			unavailable = failures.map((status: any) => skillError(status.detail ?? 'Terminal 完整包管理不可用')).join('；');
		} catch (error) {
			if (!signal.aborted) unavailable = skillError(error);
		} finally {
			if (!signal.aborted) loading = false;
		}
	};
	const itemContext = (item: any): SkillPackageContext => ({
		source: 'terminal', terminal_id: item.terminal_id ?? context.terminal_id,
		project_id: item.scope === 'project' ? item.scope_id : undefined,
		chat_id: item.scope === 'chat' ? item.scope_id : item.scope === 'global' ? context.chat_id : undefined
	});
	const reason = (item: any, action: string) => unavailable || (!item.write_access && action !== 'export' ? '此 Skill 为只读' : item.capabilities?.[action] === false ? '此 Terminal 未提供该操作' : '');
	const exportItem = async (item: any, format: 'json' | 'zip' | 'skill') => {
		try { downloadSkillBlob(await exportSkillPackage(localStorage.token, item.id, format, itemContext(item)), `${item.name}.${format}`); }
		catch (error) { toast.error(skillError(error)); }
	};
	const toggle = async (item: any) => {
		if (pending || reason(item, 'update')) return;
		pending = item.id;
		try {
			const detail = await getSkillPackage(localStorage.token, item.id, itemContext(item));
			await updateSkillPackage(localStorage.token, item.id, { is_active: !(item.is_active ?? true), expected_version_id: detail.version_id }, itemContext(item));
			await load();
		} catch (error) { toast.error(skillError(error)); }
		finally { pending = ''; }
	};
	const remove = async () => {
		if (!deleting || pending || reason(deleting, 'delete')) return;
		pending = deleting.id;
		try {
			const version = deleting.version_id ?? (await getSkillPackage(localStorage.token, deleting.id, itemContext(deleting))).version_id;
			await deleteSkillPackage(localStorage.token, deleting.id, version, itemContext(deleting));
			toast.success('Skill 已删除');
			await load();
		} catch (error) { toast.error(skillError(error)); }
		finally { pending = ''; deleting = null; }
	};
	const pickFiles = (input: HTMLInputElement) => {
		importFiles = Array.from(input.files ?? []);
		showImport = importFiles.length > 0;
		input.value = '';
	};
	onMount(load);
	onDestroy(() => controller?.abort());
</script>

<SkillImport bind:show={showImport} files={importFiles} packageContext={context} onImported={load} />
<ConfirmDialog bind:show={showDelete} title="删除整个 Skill 文件夹？" confirmLabel="删除" onConfirm={remove} />
<input type="file" multiple hidden accept=".md,.json,.zip,.skill" bind:this={importInput} on:change={() => pickFiles(importInput)} />
<input type="file" multiple hidden webkitdirectory bind:this={folderInput} on:change={() => pickFiles(folderInput)} />
<div class="flex flex-wrap items-center gap-2 pb-2 text-xs">
	<input class="min-w-32 flex-1 bg-transparent px-2 py-1.5 outline-hidden" placeholder="搜索 Skills" aria-label="搜索 Terminal Skills" bind:value={query} />
	<button type="button" class="rounded-lg px-2 py-1.5 text-gray-500 disabled:opacity-40" disabled={loading} on:click={load}>刷新</button>
	{#if canCreate}<Tooltip content={unavailable}><button type="button" class="rounded-lg bg-gray-100 px-2 py-1.5 disabled:opacity-40 dark:bg-gray-850" disabled={loading || !!unavailable} on:click={() => goto(skillPackageCreateUrl(context))}>创建</button></Tooltip>{/if}
	{#if canImport}
		<Tooltip content={unavailable}><button type="button" class="rounded-lg px-2 py-1.5 disabled:opacity-40" disabled={loading || !!unavailable} on:click={() => importInput.click()}>导入</button></Tooltip>
		<Tooltip content={unavailable}><button type="button" class="rounded-lg px-2 py-1.5 disabled:opacity-40" disabled={loading || !!unavailable} on:click={() => folderInput.click()}>导入文件夹</button></Tooltip>
	{/if}
	{#if unavailable}<Tooltip content={unavailable}><span class="text-gray-400">Terminal 不可用</span></Tooltip>{/if}
</div>
{#if loading}<div class="flex justify-center py-16"><Spinner className="size-5" /></div>
{:else}
	<div class="space-y-1">
		{#each visibleItems as item (item.id)}
			<div class="flex flex-wrap items-center gap-3 rounded-xl px-2 py-3 hover:bg-gray-50 dark:hover:bg-gray-850">
				<div class="min-w-0 flex-1">
					<a class="block truncate text-sm hover:underline" href={skillPackageEditUrl(item.id, itemContext(item))}>{item.name}</a>
					<Tooltip content={item.location ?? item.package_id ?? item.id}><div class="truncate text-xs text-gray-500">{item.location ?? item.package_id ?? item.id}</div></Tooltip>
					{#if item.description}<div class="mt-1 truncate text-xs text-gray-500">{item.description}</div>{/if}
				</div>
				<div class="flex flex-wrap items-center gap-2 text-xs">
					{#each ['chat', 'assistant', 'project'] as mode}<span class="text-gray-500" class:opacity-30={item.meta?.modes?.[mode] === false}>{mode === 'chat' ? '对话' : mode === 'assistant' ? '助手' : '项目'}</span>{/each}
					<Tooltip content={reason(item, 'update')}><button type="button" class="rounded-lg px-2 py-1 disabled:opacity-40" disabled={!!reason(item, 'update')} on:click={() => goto(skillPackageEditUrl(item.id, itemContext(item)))}>编辑</button></Tooltip>
					{#if canExport}
						{#each ['skill', 'zip', 'json'] as format}<Tooltip content={reason(item, 'export')}><button type="button" class="rounded-lg px-1 py-1 uppercase disabled:opacity-40" disabled={!!reason(item, 'export')} on:click={() => exportItem(item, format as 'skill' | 'zip' | 'json')}>{format}</button></Tooltip>{/each}
					{/if}
					<Tooltip content={reason(item, 'delete')}><button type="button" class="rounded-lg px-2 py-1 text-red-500 disabled:opacity-40" disabled={!!pending || !!reason(item, 'delete')} on:click={() => { deleting = item; showDelete = true; }}>删除</button></Tooltip>
					{#key `${item.id}:${item.is_active}:${pending}`}<Switch state={item.is_active ?? true} disabled={!!pending || !!reason(item, 'update')} tooltip={reason(item, 'update') || '启用 Skill'} ariaLabel={`启用 ${item.name}`} on:change={() => toggle(item)} />{/key}
				</div>
			</div>
		{:else}<div class="py-12 text-center text-sm text-gray-500">暂无 Skills</div>{/each}
	</div>
{/if}
