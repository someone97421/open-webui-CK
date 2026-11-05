<script lang="ts">
	import { resolveLocalizedResource } from '$lib/utils/localizedContent';
	import { getContext, onDestroy } from 'svelte';
	import { readable, type Readable } from 'svelte/store';
	import { skillAvailable, defaultAttachmentPolicy, type AttachmentPolicy } from '$lib/utils/skillPolicy';
	const attachmentPolicy = getContext<Readable<AttachmentPolicy>>('attachmentPolicy') ?? readable(defaultAttachmentPolicy);
	import { loadSkillCatalog } from '../../skillCatalog';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Cube from '$lib/components/icons/Cube.svelte';

	const i18n = getContext('i18n');

	export let query = '';
	export let onSelect = (e) => {};

	let selectedIdx = 0;
	export let filteredItems = [];

	let searchDebounceTimer: ReturnType<typeof setTimeout>;

	$: if (query !== undefined && $attachmentPolicy) {
		clearTimeout(searchDebounceTimer);
		searchDebounceTimer = setTimeout(() => {
			getItems();
		}, 200);
	}

	onDestroy(() => {
		clearTimeout(searchDebounceTimer);
	});

	let requestSequence = 0;
	const getItems = async () => {
		const sequence = ++requestSequence;
		const policy = $attachmentPolicy;
		const res = await loadSkillCatalog(localStorage.token, policy, query).catch(() => null);
		if (sequence !== requestSequence || policy !== $attachmentPolicy) return;
		filteredItems = (res?.items ?? []).filter((skill) => skillAvailable(skill, policy.mode, policy.capabilities, policy.terminalAvailable));
	};

	$: if (query) {
		selectedIdx = 0;
	}

	export const selectUp = () => {
		selectedIdx = Math.max(0, selectedIdx - 1);
	};

	export const selectDown = () => {
		selectedIdx = Math.min(selectedIdx + 1, filteredItems.length - 1);
	};

	export const select = async () => {
		const skill = filteredItems[selectedIdx];
		if (skill) {
			onSelect({ type: 'skill', data: skill });
		}
	};

	const escapeTooltipText = (value = '') =>
		String(value)
			.replaceAll('&', '&amp;')
			.replaceAll('<', '&lt;')
			.replaceAll('>', '&gt;')
			.replaceAll('"', '&quot;')
			.replaceAll("'", '&#39;');

	const getTooltipContent = (skill) => {
		const name = escapeTooltipText(resolveLocalizedResource(skill, $i18n.language));
		const description = escapeTooltipText(
			resolveLocalizedResource(skill, $i18n.language, 'description')
		);

		return `<div class="max-w-80 whitespace-normal text-left leading-snug">
			<span class="break-words font-normal">${name}</span>${description ? `: <span class="break-words opacity-80">${description}</span>` : ''}
		</div>`;
	};
</script>

<div class="app-muted mb-0.5 px-2 pt-1 pb-0.5 text-[0.625rem] leading-none">
	{$i18n.t('Skills')}
</div>

{#if filteredItems.length > 0}
	{#each filteredItems as skill, skillIdx}
		<Tooltip
			content={getTooltipContent(skill)}
			allowHTML={true}
			placement="top-start"
			tippyOptions={{ maxWidth: '20rem' }}
		>
			<button
				class="flex h-6 w-full items-center rounded-xl px-2 text-left text-[0.8125rem] transition-colors duration-75 hover:bg-gray-50/40 dark:hover:bg-gray-800/40 {skillIdx ===
				selectedIdx
					? 'app-interactive-active selected-command-option-button'
					: ''}"
				type="button"
				on:click={() => {
					onSelect({ type: 'skill', data: skill });
				}}
				on:mousemove={() => {
					selectedIdx = skillIdx;
				}}
				on:focus={() => {}}
				data-selected={skillIdx === selectedIdx}
			>
				<div class="flex w-full min-w-0 items-center gap-2">
					<div class="app-icon-muted flex w-4 shrink-0 items-center justify-center">
						<Cube className="size-3.5" />
					</div>
					<div class="truncate min-w-0 flex-1">
						{resolveLocalizedResource(skill, $i18n.language)}
					</div>
					<div class="app-muted max-w-24 shrink-0 truncate text-[0.625rem]">
						{skill.source === 'terminal' ? $i18n.t('Terminal') : skill.id}
					</div>
				</div>
			</button>
		</Tooltip>
	{/each}
{/if}
