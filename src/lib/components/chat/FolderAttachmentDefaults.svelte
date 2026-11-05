<script lang="ts">
	import { getContext, onDestroy } from 'svelte';
	import { config, models, user } from '$lib/stores';
	import { loadSkillCatalog } from './skillCatalog';
	import { getTools } from '$lib/apis/tools';
	import { getFolderAttachments, type FolderAttachments } from '$lib/apis/folders';
	import { attachmentCapabilities, canonicalSkillIds, skillAvailable, toolAvailable, type SkillMode } from '$lib/utils/skillPolicy';
	import { resolveLocalizedResource } from '$lib/utils/localizedContent';
	import Switch from '$lib/components/common/Switch.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import { toast } from 'svelte-sonner';

	export let skillIds: string[] | null | undefined = null;
	export let toolIds: string[] | null | undefined = null;
	export let folderId: string | null = null;
	export let parentId: string | null = null;
	export let project = false;
	export let terminalId = '';
	export let modelIds: string[] = [];
	export let disabled = false;
	export let loading = true;
	export let loadFailed = false;
	const i18n: any = getContext('i18n');
	const defaultsHint = '仅影响新会话，会话中可自由增减 Skill 和工具。';
	let catalog: any[] = [];
	let toolCatalog: any[] = [];
	let scope: FolderAttachments | null = null;
	let terminalOnline = false;
	let request = 0;
	let disposed = false;
	let loadedKey = '';
	$: mode = (project ? 'project' : scope?.mode ?? 'assistant') as SkillMode;
	$: selector = project ? terminalId : scope?.terminal_id;
	$: capabilities = attachmentCapabilities(modelIds.map((id) => $models.find((model) => model.id === id)).filter(Boolean), $config, $user, mode);
	$: terminalAvailable = mode === 'project' && !!selector && terminalOnline && capabilities.terminal !== false;
	$: skillDefaults = canonicalSkillIds(skillIds ?? [], catalog);
	$: toolDefaults = toolIds ?? [];
	$: skillItems = [...catalog.filter((skill) => skillAvailable(skill, mode, capabilities, terminalAvailable)),
		...skillDefaults.filter((id) => !catalog.some((skill) => skill.id === id && skillAvailable(skill, mode, capabilities, terminalAvailable))).map((id) => catalog.find((skill) => skill.id === id) ?? { id, name: id, is_active: false })];
	$: toolItems = [...toolCatalog.filter((tool) => toolAvailable(tool, capabilities)),
		...toolDefaults.filter((id) => !toolCatalog.some((tool) => tool.id === id && toolAvailable(tool, capabilities))).map((id) => toolCatalog.find((tool) => tool.id === id) ?? { id, name: id, is_active: false })];
	$: if (loadedKey !== JSON.stringify([folderId, parentId, project, terminalId])) {
		loadedKey = JSON.stringify([folderId, parentId, project, terminalId]);
		void load();
	}
	const load = async () => {
		const sequence = ++request;
		loading = true;
		loadFailed = false;
		try {
			const [tools, attachments] = await Promise.all([
				getTools(localStorage.token),
				(folderId || (!project && parentId))
					? getFolderAttachments(localStorage.token, (folderId || parentId)!)
					: Promise.resolve(null)
			]);
			if (disposed || sequence !== request) return;
			const packages = await loadSkillCatalog(localStorage.token, {
				mode: project ? 'project' : attachments?.mode ?? 'assistant',
				projectId: folderId ? attachments?.project_id : (!project ? attachments?.project_id : null),
				terminalId: project ? terminalId : attachments?.terminal_id
			});
			if (disposed || sequence !== request) return;
			scope = attachments;
			catalog = packages.items;
			terminalOnline = packages.statuses.some((status) => status.source === 'terminal' && status.available === true);
			toolCatalog = tools ?? [];
			if (skillIds == null) skillIds = folderId ? [...(attachments?.skill_ids ?? [])] : [];
			if (toolIds == null) toolIds = folderId ? [...(attachments?.tool_ids ?? [])] : [];
		} catch (error) {
			if (!disposed && sequence === request) {
				loadFailed = true;
				toast.error(`${error}`);
			}
		} finally {
			if (!disposed && sequence === request) loading = false;
		}
	};
	onDestroy(() => { disposed = true; request += 1; });
	const toggleSkill = (id: string, checked: boolean) => {
		if (disabled || loading || loadFailed) return;
		const current = canonicalSkillIds(skillIds ?? [], catalog);
		skillIds = checked ? [...new Set([...current, id])] : current.filter((value) => value !== id);
	};
	const toggleTool = (id: string, checked: boolean) => {
		if (disabled || loading || loadFailed) return;
		toolIds = checked ? [...new Set([...(toolIds ?? []), id])] : (toolIds ?? []).filter((value) => value !== id);
	};
</script>

<div class="my-2 space-y-3 text-xs" aria-busy={loading}>
	{#if loading}
		<div role="status" class="flex items-center gap-2 text-gray-500"><Spinner className="size-3" /><span>加载默认配置…</span></div>
	{:else if loadFailed}
		<button type="button" class="rounded px-1 py-1 text-gray-500 underline focus-visible:outline focus-visible:outline-2 disabled:opacity-50" disabled={disabled} title="默认配置加载失败，重试成功后可保存" on:click={load}>重新加载</button>
	{/if}
	<div>
		<div class="mb-2 text-gray-500" title={defaultsHint}>默认 Skill</div>
		<div class="grid max-h-40 grid-cols-2 gap-x-4 gap-y-2 overflow-y-auto p-1 lg:grid-cols-3">
			{#each skillItems as skill (skill.id)}
				{@const available = skillAvailable(skill, mode, capabilities, terminalAvailable)}
				{@const name = resolveLocalizedResource(skill, $i18n.language) || skill.id}
				<Tooltip className="min-w-0" content={`${name} · ${available ? defaultsHint : '当前模式、能力或权限不可用，已选配置可关闭。'}`}>
					<div class="flex min-w-0 items-center justify-between gap-2" class:opacity-40={!available}>
						<span class="min-w-0 truncate">{name}</span>
						<Switch ariaLabel={`默认 Skill：${name}`} state={skillDefaults.includes(skill.id)} disabled={disabled || loading || loadFailed || (!available && !skillDefaults.includes(skill.id))} on:change={(event) => toggleSkill(skill.id, event.detail)} />
					</div>
				</Tooltip>
			{:else}
				{#if !loading && !loadFailed}<span class="col-span-full text-gray-400" title="当前模式、能力和权限下没有可选 Skill">暂无可用 Skill</span>{/if}
			{/each}
		</div>
	</div>
	<div>
		<div class="mb-2 text-gray-500" title={defaultsHint}>默认工具</div>
		<div class="grid max-h-40 grid-cols-2 gap-x-4 gap-y-2 overflow-y-auto p-1 lg:grid-cols-3">
			{#each toolItems as tool (tool.id)}
				{@const available = toolAvailable(tool, capabilities)}
				{@const name = resolveLocalizedResource(tool, $i18n.language) || tool.id}
				<Tooltip className="min-w-0" content={`${name} · ${available ? defaultsHint : '当前模式、能力或权限不可用，已选配置可关闭。'}`}>
					<div class="flex min-w-0 items-center justify-between gap-2" class:opacity-40={!available}>
						<span class="min-w-0 truncate">{name}</span>
						<Switch ariaLabel={`默认工具：${name}`} state={toolDefaults.includes(tool.id)} disabled={disabled || loading || loadFailed || (!available && !toolDefaults.includes(tool.id))} on:change={(event) => toggleTool(tool.id, event.detail)} />
					</div>
				</Tooltip>
			{:else}
				{#if !loading && !loadFailed}<span class="col-span-full text-gray-400" title="当前能力和权限下没有可选工具">暂无可用工具</span>{/if}
			{/each}
		</div>
	</div>
</div>
