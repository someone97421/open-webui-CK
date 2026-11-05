<script lang="ts">
	import { toast } from 'svelte-sonner';
	import { goto } from '$app/navigation';
	import { skills } from '$lib/stores';
	import { onMount, getContext } from 'svelte';
	import { getSkillPackage, getSkills, updateSkillPackage, skillError, type SkillPackageContext } from '$lib/apis/skills';
	import { page } from '$app/stores';
	import SkillEditor from '$lib/components/workspace/Skills/SkillEditor.svelte';

	const i18n = getContext<any>('i18n');
	let skill: any = null;
	let disabled = false;
	let packageContext: SkillPackageContext = {};
	$: skillId = $page.url.searchParams.get('id');
	const onSubmit = async (draft: any) => {
		const updated = await updateSkillPackage(localStorage.token, skillId!, draft, packageContext);
		if (updated) {
			toast.success($i18n.t('Skill updated successfully'));
			if (updated.source !== 'terminal') skills.set(await getSkills(localStorage.token));
			skill = updated;
		}
		return updated;
	};
	onMount(async () => {
		const params = $page.url.searchParams;
		packageContext = {
			source: params.get('source') === 'terminal' ? 'terminal' : 'workspace',
			terminal_id: params.get('terminal_id') || undefined,
			project_id: params.get('project_id') || undefined,
			chat_id: params.get('chat_id') || undefined
		};
		if (!skillId) { await goto('/workspace/skills'); return; }
		try {
			skill = await getSkillPackage(localStorage.token, skillId, packageContext);
			packageContext = {
				...packageContext, source: skill.source,
				terminal_id: skill.terminal_id ?? packageContext.terminal_id,
				project_id: skill.scope === 'project' ? skill.scope_id : undefined,
				chat_id: skill.scope === 'chat' ? skill.scope_id : skill.scope === 'global' ? packageContext.chat_id : undefined
			};
			disabled = !skill.write_access;
		} catch (error) {
			toast.error(skillError(error));
			await goto('/workspace/skills');
		}
	});
</script>

{#if skill}
	<SkillEditor {skill} {onSubmit} {disabled} {packageContext} edit />
{/if}
