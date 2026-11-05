<script lang="ts">
	import { onDestroy } from 'svelte';
	import { config, models, user } from '$lib/stores';
	import { loadSkillCatalog } from './skillCatalog';
	import { getTools } from '$lib/apis/tools';
	import { getFolderAttachments, type FolderAttachments } from '$lib/apis/folders';
	import { attachmentCapabilities, canonicalSkillIds, skillAvailable, toolAvailable, type SkillMode } from '$lib/utils/skillPolicy';
	import { resolveLocalizedResource } from '$lib/utils/localizedContent';
	import { getContext } from 'svelte';
	import { toast } from 'svelte-sonner';

	export let skillIds: string[] | null | undefined = null;
	export let toolIds: string[] | null | undefined = null;
	export let folderId: string | null = null;
	export let parentId: string | null = null;
	export let project = false;
	export let terminalId = '';
	export let modelIds: string[] = [];
	export let disabled = false;
	const i18n: any = getContext('i18n');
	let catalog: any[] = [];
	let toolCatalog: any[] = [];
	let inherited: FolderAttachments | null = null;
	let scope: FolderAttachments | null = null;
	let terminalOnline = false;
	let loading = false;
	let request = 0;
	let disposed = false;
	let loadedKey = '';
	$: mode = (project ? 'project' : scope?.mode ?? 'assistant') as SkillMode;
	$: selector = project ? terminalId : scope?.terminal_id;
	$: capabilities = attachmentCapabilities(modelIds.map((id) => $models.find((model) => model.id === id)).filter(Boolean), $config, $user, mode);
	$: terminalAvailable = mode === 'project' && !!selector && terminalOnline && capabilities.terminal !== false;
	$: skillDefaults = canonicalSkillIds(skillIds ?? (project && !folderId ? [] : inherited?.skill_ids ?? []), catalog);
	$: toolDefaults = toolIds ?? (project && !folderId ? [] : inherited?.tool_ids ?? []);
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
		try {
			const [tools, attachments, parentAttachments] = await Promise.all([
				getTools(localStorage.token),
				(folderId || parentId) ? getFolderAttachments(localStorage.token, (folderId || parentId)!) : Promise.resolve(null),
				folderId && parentId && !project ? getFolderAttachments(localStorage.token, parentId) : Promise.resolve(null)
			]);
			if (disposed || sequence !== request) return;
			scope = attachments;
			inherited = folderId ? (parentAttachments?.project_id === attachments?.project_id ? parentAttachments : null) : (project ? null : attachments);
			const packages = await loadSkillCatalog(localStorage.token, {
				mode: project ? 'project' : attachments?.mode ?? 'assistant',
				projectId: folderId ? attachments?.project_id : (!project ? attachments?.project_id : null),
				terminalId: project ? terminalId : attachments?.terminal_id
			});
			if (disposed || sequence !== request) return;
			catalog = packages.items;
			terminalOnline = packages.statuses.some((status) => status.source === 'terminal' && status.available === true);
			toolCatalog = tools ?? [];
		} catch (error) {
			if (!disposed && sequence === request) toast.error(`${error}`);
		} finally {
			if (!disposed && sequence === request) loading = false;
		}
	};
	onDestroy(() => { disposed = true; request += 1; });
	const toggleSkill = (id: string, checked: boolean) => {
		const current = canonicalSkillIds(skillIds ?? [], catalog);
		skillIds = checked ? [...new Set([...current, id])] : current.filter((value) => value !== id);
	};
	const toggleTool = (id: string, checked: boolean) => {
		toolIds = checked ? [...new Set([...(toolIds ?? []), id])] : (toolIds ?? []).filter((value) => value !== id);
	};
</script>

<div class="my-2 space-y-3 text-xs">
	<div>
		<div class="mb-1 flex items-center justify-between">
			<span class="text-gray-500">默认 Skill</span>
			<label class="flex items-center gap-1" title="继承最近上级的显式配置；取消继承后可明确留空。项目不跨越项目边界继承。">
				<input type="checkbox" checked={skillIds == null} disabled={disabled || loading} on:change={(event) => { skillIds = event.currentTarget.checked ? null : [...skillDefaults]; }} />继承上级
			</label>
		</div>
		<div class="max-h-32 overflow-y-auto space-y-1">
			{#each skillItems as skill (skill.id)}
				{@const available = skillAvailable(skill, mode, capabilities, terminalAvailable)}
				<label class="flex items-center gap-2" class:opacity-40={!available} title={!available ? '当前模式、能力或权限不可用，配置已保留' : skillIds == null ? `继承来源：${inherited?.skill_source_id ?? '无'}` : '分组默认'}>
					<input type="checkbox" checked={skillDefaults.includes(skill.id)} disabled={disabled || loading || skillIds == null || (!available && !skillDefaults.includes(skill.id))} on:change={(event) => toggleSkill(skill.id, event.currentTarget.checked)} />
					<span class="truncate">{resolveLocalizedResource(skill, $i18n.language) || skill.id}</span>
				</label>
			{/each}
		</div>
	</div>
	<div>
		<div class="mb-1 flex items-center justify-between">
			<span class="text-gray-500">默认工具</span>
			<label class="flex items-center gap-1" title="继承最近上级的显式配置；取消继承后可明确留空。项目不跨越项目边界继承。">
				<input type="checkbox" checked={toolIds == null} disabled={disabled || loading} on:change={(event) => { toolIds = event.currentTarget.checked ? null : [...toolDefaults]; }} />继承上级
			</label>
		</div>
		<div class="max-h-32 overflow-y-auto space-y-1">
			{#each toolItems as tool (tool.id)}
				{@const available = toolAvailable(tool, capabilities)}
				<label class="flex items-center gap-2" class:opacity-40={!available} title={!available ? '当前模式、能力或权限不可用，配置已保留' : toolIds == null ? `继承来源：${inherited?.tool_source_id ?? '无'}` : '分组默认'}>
					<input type="checkbox" checked={toolDefaults.includes(tool.id)} disabled={disabled || loading || toolIds == null || (!available && !toolDefaults.includes(tool.id))} on:change={(event) => toggleTool(tool.id, event.currentTarget.checked)} />
					<span class="truncate">{resolveLocalizedResource(tool, $i18n.language) || tool.id}</span>
				</label>
			{/each}
		</div>
	</div>
</div>
