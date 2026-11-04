<script lang="ts">
	import { onDestroy } from 'svelte';
	import { toast } from 'svelte-sonner';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import { getProjectAgents, updateProjectAgents } from '$lib/apis/terminal';

	export let projectId: string;
	export let readOnly = false;
	export let disabled = false;
	export let saving = false;
	export let saveBlocked = false;

	let loadedProjectId: string | null = null;
	let content = '';
	let savedContent = '';
	let exists: boolean | null = null;
	let loading = true;
	let loadError = '';
	let requestSequence = 0;

	$: dirty = content !== savedContent;
	$: tooLarge = new TextEncoder().encode(content).length > 32 * 1024;
	$: saveBlocked = dirty && tooLarge;

	const isCurrent = (sequence: number, id: string) =>
		sequence === requestSequence && loadedProjectId === id && projectId === id;

	const load = async (id: string) => {
		const sequence = ++requestSequence;
		loading = true;
		saving = false;
		loadError = '';
		exists = null;
		content = '';
		savedContent = '';
		try {
			const result = await getProjectAgents(localStorage.token, id);
			if (!isCurrent(sequence, id)) return;
			content = result.content;
			savedContent = result.content;
			exists = result.exists;
		} catch (error) {
			if (!isCurrent(sequence, id)) return;
			loadError = error instanceof Error ? error.message : String(error);
			toast.error(`AGENTS.md 加载失败：${loadError}`);
		} finally {
			if (isCurrent(sequence, id)) loading = false;
		}
	};

	const persist = async (create = false): Promise<boolean> => {
		if (!projectId || readOnly || loading || saving || loadError) return false;
		if (create ? exists !== false : exists !== true || !dirty) return false;
		if (tooLarge) {
			toast.error('AGENTS.md 不能超过 32 KiB');
			return false;
		}
		const id = projectId;
		const sequence = ++requestSequence;
		const nextContent = create ? '' : content;
		saving = true;
		try {
			const result = await updateProjectAgents(localStorage.token, id, nextContent);
			if (!isCurrent(sequence, id)) return false;
			content = result.content;
			savedContent = result.content;
			exists = result.exists;
			toast.success(create ? 'AGENTS.md 已创建' : 'AGENTS.md 已保存');
			return true;
		} catch (error) {
			if (isCurrent(sequence, id)) {
				toast.error(`AGENTS.md ${create ? '创建' : '保存'}失败：${error instanceof Error ? error.message : String(error)}`);
			}
			return false;
		} finally {
			if (isCurrent(sequence, id)) saving = false;
		}
	};

	export const save = async (): Promise<boolean> => {
		if (!dirty) return true;
		return persist();
	};

	$: if (projectId && projectId !== loadedProjectId) {
		loadedProjectId = projectId;
		void load(projectId);
	}

	onDestroy(() => {
		requestSequence += 1;
	});
</script>

<section class="rounded-xl border border-gray-100/80 dark:border-gray-850/60" aria-label="AGENTS.md">
	<div class="flex min-h-10 items-center justify-between gap-3 border-b border-gray-100/80 px-3 py-1.5 dark:border-gray-850/60">
		<div class="flex min-w-0 items-center gap-2">
			<h3 class="truncate text-xs font-medium text-gray-700 dark:text-gray-200" title="项目工作区中的 AGENTS.md">AGENTS.md</h3>
			{#if saving}
				<span class="text-[0.6875rem] text-gray-400" role="status">保存中…</span>
			{:else if dirty && !loading && !loadError}
				<span class="text-[0.6875rem] text-gray-400" role="status">未保存</span>
			{/if}
		</div>
		{#if exists === false && !loading && !loadError}
			<Tooltip content={readOnly ? '恢复项目后可创建 AGENTS.md' : '在项目工作区创建空的 AGENTS.md'} placement="top">
				<button
					type="button"
					class="flex h-7 shrink-0 items-center justify-center gap-1.5 rounded-lg bg-gray-900 px-2.5 text-xs text-white transition-colors duration-150 hover:bg-black disabled:cursor-not-allowed disabled:opacity-40 dark:bg-gray-100 dark:text-gray-900 dark:hover:bg-white"
					disabled={readOnly || disabled || saving}
					on:click={() => persist(true)}
				>
					{#if saving}<Spinner className="size-3" />{/if}
					创建 AGENTS.md
				</button>
			</Tooltip>
		{:else if exists === true}
			<Tooltip
				content={readOnly ? '恢复项目后可编辑 AGENTS.md' : tooLarge ? 'AGENTS.md 不能超过 32 KiB' : '保存 AGENTS.md（Ctrl/⌘ + S）'}
				placement="top"
			>
				<button
					type="button"
					class="flex h-7 shrink-0 items-center justify-center gap-1.5 rounded-lg bg-gray-900 px-2.5 text-xs text-white transition-colors duration-150 hover:bg-black disabled:cursor-not-allowed disabled:opacity-40 dark:bg-gray-100 dark:text-gray-900 dark:hover:bg-white"
					disabled={readOnly || disabled || loading || saving || !dirty || !!loadError || tooLarge}
					on:click={save}
				>
					{#if saving}<Spinner className="size-3" />{/if}
					保存
				</button>
			</Tooltip>
		{/if}
	</div>

	{#if loading}
		<div class="flex min-h-48 items-center justify-center" aria-label="正在加载 AGENTS.md">
			<Spinner className="size-4" />
		</div>
	{:else if loadError}
		<div class="flex min-h-48 flex-col items-center justify-center gap-2 px-4" role="alert">
			<span class="text-xs text-gray-500 dark:text-gray-400" title={loadError}>AGENTS.md 加载失败</span>
			<button
				type="button"
				class="rounded-lg px-2.5 py-1 text-xs text-gray-600 transition-colors duration-150 hover:bg-gray-100 disabled:opacity-40 dark:text-gray-300 dark:hover:bg-gray-850"
				disabled={disabled}
				on:click={() => load(projectId)}
			>
				重试
			</button>
		</div>
	{:else}
		<textarea
			class="block min-h-48 w-full resize-y rounded-b-xl bg-transparent px-3 py-2.5 font-mono text-xs leading-5 text-gray-700 outline-none placeholder:text-gray-400 focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-gray-300 disabled:cursor-not-allowed disabled:bg-gray-50 disabled:opacity-60 dark:text-gray-200 dark:placeholder:text-gray-600 dark:focus-visible:ring-gray-700 dark:disabled:bg-gray-900"
			bind:value={content}
			disabled={readOnly || disabled || saving || exists !== true}
			placeholder={exists === false ? '尚未创建 AGENTS.md' : '输入项目指令…'}
			aria-label="AGENTS.md 内容"
			title={readOnly ? '恢复项目后可编辑 AGENTS.md' : exists === false ? '请先创建 AGENTS.md' : tooLarge ? 'AGENTS.md 不能超过 32 KiB' : 'AGENTS.md'}
			spellcheck="false"
			on:keydown={(event) => {
				if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') {
					event.preventDefault();
					if (!disabled) void save();
				}
			}}
		></textarea>
	{/if}
</section>
