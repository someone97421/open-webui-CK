<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import Switch from '$lib/components/common/Switch.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import { getSkillBindings, setSkillBinding, skillError, type SkillBinding } from '$lib/apis/skills';

	export let skillId: string;
	export let modes: Record<string, boolean> = {};
	export let savedModes: Record<string, boolean> = {};
	export let disabled = false;
	export let skill: any = null;
	export let requirements: string[] = [];
	let items: SkillBinding[] = [];
	let loading = false;
	let error = '';
	let pending = '';
	const groups = [{ mode: 'assistant', label: '助手' }, { mode: 'project', label: '项目' }];
	const load = async () => {
		loading = true;
		error = '';
		try { items = (await getSkillBindings(localStorage.token, skillId)).items; }
		catch (err) { error = skillError(err); }
		finally { loading = false; }
	};
	const reason = (item: SkillBinding) => {
		if (disabled) return '历史版本不可更改挂载';
		if (!item.write_access) return '无分组写入权限';
		if (!item.bound && modes[item.mode] === false) return '此 Skill 未启用该模式';
		if (!item.bound && savedModes[item.mode] === false) return '请先保存模式设置';
		if (!item.bound && skill?.is_active === false) return '此 Skill 已停用';
		if (!item.bound && skill?.source === 'terminal' &&
			(skill.scope !== 'project' || skill.scope_id !== item.project_id || skill.terminal_id !== item.terminal_id)) return '只能挂载到所属项目';
		if (!item.bound && !item.terminal_id && [...requirements, ...(skill?.meta?.requires ?? [])].includes('terminal')) return '此 Skill 需要项目 Terminal';
		return '';
	};
	const toggle = async (item: SkillBinding) => {
		if (pending || reason(item)) return;
		pending = item.id;
		try {
			await setSkillBinding(localStorage.token, item.id, skillId, !item.bound);
			await load();
		} catch (err) { toast.error(skillError(err)); }
		finally { pending = ''; }
	};
	onMount(load);
</script>

<details class="shrink-0 rounded-xl border border-gray-100 px-3 py-2 text-xs dark:border-gray-800">
	<summary class="cursor-pointer text-gray-600 dark:text-gray-300">助手与项目挂载</summary>
	<div class="mt-2 max-h-48 overflow-y-auto">
		{#if loading}<Spinner className="size-3" />
		{:else if error}
			<Tooltip content={error}><button type="button" class="text-gray-500" on:click={load}>加载失败，重试</button></Tooltip>
		{:else}
			{#each groups as group}
				<div class="mb-2">
					<div class="mb-1 text-gray-500">{group.label}</div>
					{#each items.filter((item) => item.mode === group.mode && (item.write_access || item.bound)) as item (item.id)}
						<div class="flex items-center justify-between gap-2 py-1" class:opacity-50={modes[item.mode] === false}>
							<Tooltip content={item.inherited ? `继承来源：${item.source_id ?? ''}；更改后保存此分组的独立关联` : item.name}>
								<span class="truncate">{item.name}{item.inherited ? ' · 继承' : ''}</span>
							</Tooltip>
							{#key `${item.id}:${item.bound}:${pending}`}
								<Switch state={item.bound} disabled={!!pending || !!reason(item)} tooltip={reason(item) || (item.bound ? '解除挂载' : '挂载')} ariaLabel={`${group.label} ${item.name}`} on:change={() => toggle(item)} />
							{/key}
						</div>
					{:else}<span class="text-gray-400">暂无可管理分组</span>{/each}
				</div>
			{/each}
		{/if}
	</div>
</details>
