<script lang="ts">
	import { resolveLocalizedResource } from '$lib/utils/localizedContent';
	import { getContext } from 'svelte';
	import { skills, terminalSkills } from '$lib/stores';
	import { readable, type Readable } from 'svelte/store';
	import { skillAvailable, scopedSkills, defaultAttachmentPolicy, type AttachmentPolicy } from '$lib/utils/skillPolicy';
	const attachmentPolicy = getContext<Readable<AttachmentPolicy>>('attachmentPolicy') ?? readable(defaultAttachmentPolicy);

	import Modal from '../common/Modal.svelte';
	import Collapsible from '../common/Collapsible.svelte';
	import XMark from '$lib/components/icons/XMark.svelte';

	export let show = false;
	export let selectedSkillIds = [];

	let selectedSkills = [];

	$: selectedSkills = selectedSkillIds.map((id) => scopedSkills($skills ?? [], $terminalSkills ?? []).find((skill) => skill.id === id) ?? { id, name: id, is_active: false });

	const i18n = getContext('i18n');
</script>

<Modal ariaLabel={$i18n.t('Available Skills')} bind:show size="md">
	<div>
		<div class=" flex justify-between dark:text-gray-300 px-4 pt-3 pb-1">
			<div class=" text-sm font-medium self-center">{$i18n.t('Available Skills')}</div>
			<button
				class="self-center rounded-lg py-1 text-gray-500 transition hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 px-0"
				aria-label={$i18n.t('Close')}
				on:click={() => {
					show = false;
				}}
			>
				<XMark className={'size-4'} />
			</button>
		</div>

		{#if selectedSkills.length > 0}
			<div class=" flex justify-between dark:text-gray-300 px-5 pb-1">
				<div class=" text-base font-normal self-center">{$i18n.t('Skills')}</div>
			</div>

			<div class="px-5 pb-5 w-full flex flex-col justify-center">
				<div class=" text-sm dark:text-gray-300 mb-1">
					{#each selectedSkills as skill}
						<Collapsible buttonClassName="w-full mb-0.5">
							<div class="truncate" class:opacity-40={!skillAvailable(skill, $attachmentPolicy.mode, $attachmentPolicy.capabilities, $attachmentPolicy.terminalAvailable)} title={!skillAvailable(skill, $attachmentPolicy.mode, $attachmentPolicy.capabilities, $attachmentPolicy.terminalAvailable) ? '当前模式、能力或权限不可用，配置已保留' : ($attachmentPolicy.skillSources?.[skill.id] ?? '会话手动选择')}>
								<div class="text-sm font-normal dark:text-gray-100 text-gray-800 truncate">
									{resolveLocalizedResource(skill, $i18n.language)}
								</div>

								{#if resolveLocalizedResource(skill, $i18n.language, 'description')}
									<div class="text-xs text-gray-500">
										{resolveLocalizedResource(skill, $i18n.language, 'description')}
									</div>
								{/if}
								{#if skill.source === 'terminal'}
									<div class="text-xs text-gray-500">{$i18n.t('Terminal')}</div>
								{/if}
							</div>
						</Collapsible>
					{/each}
				</div>
			</div>
		{/if}
	</div>
</Modal>
