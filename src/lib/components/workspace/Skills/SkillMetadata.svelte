<script lang="ts">
	import Switch from '$lib/components/common/Switch.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	export let meta: Record<string, any> = {};
	export let disabled = false;
	const modes = [{ id: 'chat', label: '对话' }, { id: 'assistant', label: '助手' }, { id: 'project', label: '项目' }];
	const capabilities = ['terminal', 'code_interpreter', 'web_search', 'image_generation', 'builtin_tools'];
	let customRequirement = '';
	const setMode = (mode: string, enabled: boolean) => {
		meta = { ...meta, modes: { chat: true, assistant: true, project: true, ...meta.modes, [mode]: enabled } };
	};
	const toggleRequirement = (capability: string) => {
		const requires: string[] = Array.isArray(meta.requires) ? meta.requires : [];
		meta = { ...meta, requires: requires.includes(capability) ? requires.filter((item) => item !== capability) : [...requires, capability] };
	};
	const addRequirement = () => {
		const value = customRequirement.trim();
		if (disabled || !value) return;
		meta = { ...meta, requires: [...new Set([...(meta.requires ?? []), value])] };
		customRequirement = '';
	};
</script>

<div class="flex shrink-0 flex-wrap items-center gap-x-5 gap-y-2 px-1 py-2 text-xs">
	{#each modes as mode}
		<div class="flex items-center gap-2">
			<span>{mode.label}</span>
			<Switch state={meta.modes?.[mode.id] !== false} {disabled} ariaLabel={`${mode.label}模式`} on:change={(event) => setMode(mode.id, event.detail)} />
		</div>
	{/each}
	<details class="w-full">
		<summary class="w-fit cursor-pointer text-gray-500">能力需求{meta.requires?.length ? ` · ${meta.requires.length}` : ''}</summary>
		<div class="mt-2 flex flex-wrap items-center gap-2">
			{#each [...new Set([...capabilities, ...(meta.requires ?? [])])] as capability}
				<label class="flex items-center gap-1.5 rounded-lg bg-gray-50 px-2 py-1 font-mono text-gray-600 dark:bg-gray-850 dark:text-gray-300">
					<input type="checkbox" checked={meta.requires?.includes(capability) ?? false} {disabled} on:change={() => toggleRequirement(capability)} />
					{capability}
				</label>
			{/each}
			<Tooltip content="仅填写 Skill 明确需要的能力；未声明时不限制，不根据脚本推断。">
				<input class="w-40 rounded-lg bg-transparent px-2 py-1 outline-hidden" placeholder="其他能力名称" aria-label="其他能力名称" bind:value={customRequirement} {disabled} on:keydown={(event) => { if (event.key === 'Enter') { event.preventDefault(); addRequirement(); } }} />
			</Tooltip>
			<button type="button" class="px-2 py-1 text-gray-500 disabled:opacity-40" disabled={disabled || !customRequirement.trim()} on:click={addRequirement}>添加</button>
		</div>
	</details>
</div>
