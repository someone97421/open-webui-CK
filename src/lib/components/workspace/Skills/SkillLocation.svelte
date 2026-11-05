<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { getTerminalServers, type TerminalServer } from '$lib/apis/terminal';
	import { getFolders } from '$lib/apis/folders';
	import { getChatList } from '$lib/apis/chats';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import type { SkillPackageContext } from '$lib/apis/skills';
	import { isProjectFolder, getFolderProject } from '$lib/utils/projects';

	export let context: SkillPackageContext = { source: 'workspace' };
	export let onChange: () => void = () => {};
	let servers: TerminalServer[] = [];
	let projects: any[] = [];
	let chats: any[] = [];
	let loading = true;
	let error = '';
	const change = (values: Partial<SkillPackageContext>) => {
		const selectedProject = values.project_id
			? projects.find((project) => project.id === values.project_id)
			: null;
		const projectTerminal = getFolderProject(selectedProject)?.terminal_id;
		context = {
			...context, ...values,
			...(projectTerminal ? { terminal_id: projectTerminal, chat_id: undefined } : {})
		};
		if (values.terminal_id && context.project_id &&
			getFolderProject(projects.find((project) => project.id === context.project_id))?.terminal_id !== values.terminal_id
		) context = { ...context, project_id: undefined };
		onChange();
	};
	const selectScope = (value: string) => {
		change({
			project_id: value.startsWith('project:') ? value.slice(8) : undefined,
			chat_id: value.startsWith('chat:') ? value.slice(5) : undefined
		});
	};
	onMount(async () => {
		const params = $page.url.searchParams;
		context = {
			...context,
			source: params.get('source') === 'terminal' ? 'terminal' : context.source ?? 'workspace',
			terminal_id: params.get('terminal_id') || context.terminal_id,
			project_id: params.get('project_id') || context.project_id,
			chat_id: params.get('chat_id') || context.chat_id
		};
		const results = await Promise.allSettled([
			getTerminalServers(localStorage.token), getFolders(localStorage.token),
			getChatList(localStorage.token, null, true, true)
		]);
		if (results[0].status === 'fulfilled') servers = results[0].value;
		else error = '无法读取 Terminal 位置';
		if (results[1].status === 'fulfilled') projects = (results[1].value ?? []).filter(isProjectFolder);
		if (results[2].status === 'fulfilled') chats = (results[2].value ?? []).filter(
			(chat: any) => !projects.some((project) => project.id === chat.folder_id)
		);
		const projectTerminal = getFolderProject(projects.find((project) => project.id === context.project_id))?.terminal_id;
		if (projectTerminal) context = { ...context, terminal_id: projectTerminal, chat_id: undefined };
		else if (!context.terminal_id && servers.length) context = { ...context, terminal_id: servers[0].id };
		loading = false;
		onChange();
	});
</script>

<div class="flex flex-wrap items-center gap-2 py-2 text-xs">
	<select aria-label="Skill 来源" class="rounded-lg bg-gray-50 px-2 py-1.5 dark:bg-gray-850"
		value={context.source ?? 'workspace'}
		on:change={(event) => change({ source: event.currentTarget.value as 'workspace' | 'terminal' })}>
		<option value="workspace">Workspace</option>
		<option value="terminal">Terminal</option>
	</select>
	{#if context.source === 'terminal'}
		<Tooltip content={error || (!servers.length ? '暂无可用 Terminal' : 'Terminal 位置')}>
			<select aria-label="Terminal 位置"
				class="max-w-64 rounded-lg bg-gray-50 px-2 py-1.5 disabled:opacity-40 dark:bg-gray-850"
				disabled={loading || !servers.length} value={context.terminal_id ?? ''}
				on:change={(event) => change({ terminal_id: event.currentTarget.value })}>
				{#if context.terminal_id && !servers.some((server) => server.id === context.terminal_id)}
					<option value={context.terminal_id}>{context.terminal_id}</option>
				{/if}
				{#each servers as server}<option value={server.id}>{server.name || server.id}</option>{/each}
			</select>
		</Tooltip>
		<select aria-label="Skill 作用域" class="max-w-64 rounded-lg bg-gray-50 px-2 py-1.5 dark:bg-gray-850"
			value={context.project_id ? `project:${context.project_id}` : context.chat_id ? `chat:${context.chat_id}` : ''}
			on:change={(event) => selectScope(event.currentTarget.value)}>
			<option value="">全局</option>
			<optgroup label="项目">
				{#if context.project_id && !projects.some((project) => project.id === context.project_id)}
					<option value={`project:${context.project_id}`}>{context.project_id}</option>
				{/if}
				{#each projects as project}<option value={`project:${project.id}`}>{project.name}</option>{/each}
			</optgroup>
			<optgroup label="对话">
				{#if context.chat_id && !chats.some((chat) => chat.id === context.chat_id)}
					<option value={`chat:${context.chat_id}`}>{context.chat_id}</option>
				{/if}
				{#each chats as chat}<option value={`chat:${chat.id}`}>{chat.title || chat.id}</option>{/each}
			</optgroup>
		</select>
	{/if}
</div>
