<script lang="ts">
	import { getContext, onDestroy } from 'svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Image from '$lib/components/common/Image.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import GarbageBin from '$lib/components/icons/GarbageBin.svelte';
	import EditPencil from '$lib/components/icons/EditPencil.svelte';
	import ArrowForward from '$lib/components/icons/ArrowForward.svelte';
	import { WEBUI_API_BASE_URL } from '$lib/constants';
	import { isRasterImageContentType } from '$lib/utils';

	const i18n = getContext<any>('i18n');

	export let id: string;
	export let content: string;
	export let files: any[] = [];
	export let onSendNow: (id: string) => void;
	export let onEdit: ((id: string, content?: string | null) => void) | undefined = undefined;
	export let onEditStart: ((id: string) => void) | undefined = undefined;
	export let onDelete: (id: string) => void;
	export let onMove: ((id: string, direction: number) => void) | undefined = undefined;
	export let canMoveUp = false;
	export let canMoveDown = false;
	export let sending = false;
	export let deliveryPending = false;
	export let error = '';

	let editing = false;
	let editedContent = '';
	$: uploadFailed = files.some((file) => file.status === 'error');
	onDestroy(() => { if (editing) onEdit?.(id, null); });
	$: sendDisabled = sending || editing || files.some((file) => ['uploading', 'error'].includes(file.status));
	$: sendLabel = sending ? $i18n.t('Sending...') : uploadFailed ? $i18n.t('Upload failed') :
		sendDisabled && !editing ? $i18n.t('Waiting for upload') : $i18n.t('Send now');
</script>

<div class="flex items-center gap-2 px-2 py-1.5">
	<div class="shrink-0 text-gray-500"><ArrowForward className="size-3.5" /></div>
	<div class="flex-1 min-w-0 flex items-center gap-2">
		{#if files.length > 0}
			<div class="flex items-center gap-1 shrink-0">
				{#each files as file}
					{#if file.type === 'image' || isRasterImageContentType(file?.content_type)}
						{@const fileUrl = file.url?.startsWith('data') || file.url?.startsWith('http')
							? file.url : `${WEBUI_API_BASE_URL}/files/${file.url}${file?.content_type ? '/content' : ''}`}
						<div class="relative size-6 shrink-0 overflow-hidden rounded-lg border border-gray-100/60 bg-white/60 dark:border-white/[0.06] dark:bg-white/[0.025]">
							<Image src={fileUrl} alt="" imageClassName="size-full object-cover" />
							{#if file.status === 'uploading'}<Spinner className="size-3" />{/if}
						</div>
					{:else}
						<div class="flex h-6 max-w-[9rem] items-center gap-1 rounded-lg border border-gray-100/60 bg-white/60 px-1.5 text-[0.6875rem] text-gray-500 dark:border-white/[0.06] dark:bg-white/[0.025]">
							{#if file.status === 'uploading'}<Spinner className="size-3" />{/if}
							<span class="max-w-[5rem] truncate">{file.name ?? 'file'}</span>
						</div>
					{/if}
				{/each}
			</div>
		{/if}
		{#if editing}
			<textarea class="min-w-0 flex-1 resize-y rounded-lg bg-transparent text-sm outline-none" rows="2" bind:value={editedContent} aria-label={$i18n.t('Edit')} />
		{:else if content}
			<p class="truncate text-sm text-gray-600 dark:text-gray-300">{content}</p>
		{:else if files.length === 0}
			<p class="truncate text-sm italic text-gray-400 dark:text-gray-500">{$i18n.t('Empty message')}</p>
		{/if}
		{#if uploadFailed}
			<span class="shrink-0 text-xs text-gray-400">{$i18n.t('Upload failed')}</span>
		{:else if error}
			<Tooltip content={error}><span class="shrink-0 text-xs text-red-500">{$i18n.t('Failed to send message')}</span></Tooltip>
		{:else if sending}
			<Spinner className="size-3 shrink-0" />
		{/if}
	</div>
	<div class="flex shrink-0 items-center gap-1">
		{#if editing}
			<button type="button" class="p-1 text-xs text-gray-500 hover:text-gray-700" disabled={!editedContent.trim() && files.length === 0} on:click={() => { onEdit?.(id, editedContent); editing = false; }}>{$i18n.t('Save')}</button>
			<button type="button" class="p-1 text-xs text-gray-500 hover:text-gray-700" on:click={() => { onEdit?.(id, null); editing = false; }}>{$i18n.t('Cancel')}</button>
		{:else}
			{#if onMove}
				<Tooltip content={$i18n.t('Move up')}>
					<button type="button" aria-label={$i18n.t('Move up')} class="p-1 text-gray-400 hover:text-gray-700 disabled:opacity-40" disabled={sending || !canMoveUp} on:click={() => onMove?.(id, -1)}>
						<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" class="size-3.5"><path stroke-linecap="round" stroke-linejoin="round" d="m5 15 7-7 7 7" /></svg>
					</button>
				</Tooltip>
				<Tooltip content={$i18n.t('Move down')}>
					<button type="button" aria-label={$i18n.t('Move down')} class="p-1 text-gray-400 hover:text-gray-700 disabled:opacity-40" disabled={sending || !canMoveDown} on:click={() => onMove?.(id, 1)}>
						<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" class="size-3.5"><path stroke-linecap="round" stroke-linejoin="round" d="m5 9 7 7 7-7" /></svg>
					</button>
				</Tooltip>
			{/if}
			<Tooltip content={sendLabel}>
				<button type="button" aria-label={sendLabel} class="p-1 text-gray-400 hover:text-gray-700 disabled:opacity-40" disabled={sendDisabled} on:click={() => onSendNow(id)}>
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" class="size-3.5"><path stroke-linecap="round" stroke-linejoin="round" d="M4.5 10.5 12 3m0 0 7.5 7.5M12 3v18" /></svg>
				</button>
			</Tooltip>
			<Tooltip content={$i18n.t('Edit')}>
				<button type="button" aria-label={$i18n.t('Edit')} class="p-1 text-gray-400 hover:text-gray-700 disabled:opacity-40" disabled={sending || deliveryPending || !onEdit} on:click={() => { if (onEditStart) { editedContent = content; onEditStart(id); editing = true; } else onEdit?.(id); }}><EditPencil className="size-3.5" /></button>
			</Tooltip>
			<Tooltip content={$i18n.t('Delete')}>
				<button type="button" aria-label={$i18n.t('Delete')} class="p-1 text-gray-400 hover:text-gray-700 disabled:opacity-40" disabled={sending || deliveryPending} on:click={() => onDelete(id)}><GarbageBin className="size-3.5" /></button>
			</Tooltip>
		{/if}
	</div>
</div>
