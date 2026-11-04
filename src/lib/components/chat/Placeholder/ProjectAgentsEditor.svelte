<script lang="ts">
	import { toast } from 'svelte-sonner';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import { getProjectAgents, updateProjectAgents } from '$lib/apis/terminal';

	export let projectId: string;
	export let readOnly = false;

	let loadedProjectId: string | null = null;
	let content = '';
	let savedContent = '';
	let loading = false;
	let saving = false;
	let loadError = '';
	let requestSequence = 0;

	$: dirty = content !== savedContent;

	$: tooLarge = new TextEncoder().encode(content).length > 32 * 1024;
	const load = async (id: string) => {
		const sequence = ++requestSequence;
		loading = true;
		loadError = '';
		try {
			const result = await getProjectAgents(localStorage.token, id);
			if (sequence !== requestSequence || loadedProjectId !== id) return;
			content = result.content;
			savedContent = result.content;
		} catch (error) {
			if (sequence !== requestSequence || loadedProjectId !== id) return;
			loadError = error instanceof Error ? error.message : String(error);
			toast.error(`AGENTS.md 加载失败：${loadError}`);
		} finally {
			if (sequence === requestSequence) loading = false;
		}
	};

	const save = async () => {
		if (!projectId || readOnly || loading || saving || !dirty || loadError) return;
		const id = projectId;
		if (tooLarge) {
			toast.error('AGENTS.md 不能超过 32 KiB');
			return;
		}
		const nextContent = content;
		saving = true;
		try {
			const result = await updateProjectAgents(localStorage.token, id, nextContent);
			if (loadedProjectId !== id) return;
			content = result.content;
			savedContent = result.content;
			toast.success('AGENTS.md 已保存');
		} catch (error) {
			toast.error(`AGENTS.md 保存失败：${error instanceof Error ? error.message : String(error)}`);
		} finally {
			saving = false;
		}
	};

	$: if (projectId && projectId !== loadedProjectId) {
		loadedProjectId = projectId;
		content = '';
		savedContent = '';
		void load(projectId);
	}
</script>

<section class="rounded-xl border border-gray-100/80 dark:border-gray-850/60" aria-label="AGENTS.md">
	<div class="flex min-h-10 items-center justify-between gap-3 border-b border-gray-100/80 px-3 py-1.5 dark:border-gray-850/60">
		<div class="flex min-w-0 items-center gap-2">
			<h3 class="truncate text-xs font-medium text-gray-700 dark:text-gray-200">AGENTS.md</h3>
			{#if saving}
				<span class="text-[0.6875rem] text-gray-400" role="status">保存中…</span>
			{:else if dirty && !loading && !loadError}
				<span class="text-[0.6875rem] text-gray-400" role="status">未保存</span>
			{/if}
		</div>
		<Tooltip
			content={readOnly ? '只读项目' : tooLarge ? 'AGENTS.md 不能超过 32 KiB' : '保存 AGENTS.md（Ctrl/⌘ + S）'}
			placement="top"
		>
			<button
				type="button"
				class="flex h-7 shrink-0 items-center justify-center gap-1.5 rounded-lg bg-gray-900 px-2.5 text-xs text-white transition-colors duration-150 hover:bg-black disabled:cursor-not-allowed disabled:opacity-40 dark:bg-gray-100 dark:text-gray-900 dark:hover:bg-white"
				disabled={readOnly || loading || saving || !dirty || !!loadError || tooLarge}
				on:click={save}
			>
				{#if saving}<Spinner className="size-3" />{/if}
				保存
			</button>
		</Tooltip>
	</div>

	{#if loading}
		<div class="flex min-h-52 items-center justify-center" aria-label="正在加载 AGENTS.md">
			<Spinner className="size-4" />
		</div>
	{:else if loadError}
		<div class="flex min-h-52 flex-col items-center justify-center gap-2 px-4" role="alert">
			<span class="text-xs text-gray-500 dark:text-gray-400">AGENTS.md 加载失败</span>
			<button
				type="button"
				class="rounded-lg px-2.5 py-1 text-xs text-gray-600 transition-colors duration-150 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-850"
				on:click={() => load(projectId)}
			>
				重试
			</button>
		</div>
	{:else}
		<textarea
			class="block min-h-52 w-full resize-y rounded-b-xl bg-transparent px-3 py-2.5 font-mono text-xs leading-5 text-gray-700 outline-none placeholder:text-gray-300 focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-gray-300 disabled:cursor-not-allowed disabled:opacity-60 dark:text-gray-200 dark:placeholder:text-gray-700 dark:focus-visible:ring-gray-700"
			bind:value={content}
			disabled={readOnly || saving}
			placeholder="输入项目指令…"
			aria-label="AGENTS.md 内容"
			spellcheck="false"
			on:keydown={(event) => {
				if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') {
					event.preventDefault();
					void save();
				}
			}}
		></textarea>
	{/if}
</section>
