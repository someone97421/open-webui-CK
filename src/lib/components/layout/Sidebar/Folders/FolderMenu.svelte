<script lang="ts">
	import { getContext, createEventDispatcher } from 'svelte';

	const i18n = getContext('i18n');
	const dispatch = createEventDispatcher();

	import { user } from '$lib/stores';

	import Dropdown from '$lib/components/common/Dropdown.svelte';
	import DropdownMenu from '$lib/components/common/DropdownMenu.svelte';
	import EditPencil from '../icons/EditPencil.svelte';
	import FolderIcon from '../icons/Folder.svelte';
	import TrashIcon from '../icons/Trash.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Download from '../icons/Download.svelte';
	import CheckIcon from '$lib/components/icons/Check.svelte';
	import ArchiveIcon from '../icons/Archive.svelte';

	export let align: 'start' | 'end' = 'start';
	export let onNewChat: (() => void) | null = null;
	export let onEdit = () => {};
	export let onExport = () => {};
	export let onDelete = () => {};
	export let onArchive = () => {};
	export let canDelete = true;
	export let onCreateSubFolder = () => {};
	export let onMarkAllRead = () => {};
	export let onRestore = () => {};
	export let isProject = false;
	export let projectArchived = false;
	let show = false;
</script>

<Dropdown
	closeOnSelect
	bind:show
	{align}
	onOpenChange={(state) => {
		if (state === false) {
			dispatch('close');
		}
	}}
>
	<Tooltip content={$i18n.t('More')}>
		<button
			type="button"
			aria-label={isProject ? '项目选项' : $i18n.t('Folder options')}
			on:click={(e) => {
				e.stopPropagation();
				show = !show;
			}}
		>
			<slot />
		</button>
	</Tooltip>

	<div slot="content">
		<DropdownMenu className="min-w-[10.625rem]">
			{#if onNewChat && !projectArchived}
				<button
					type="button"
					class="flex h-[1.6875rem] w-full items-center gap-2 rounded-xl px-2 text-[0.8125rem] select-none cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-900"
					on:click={onNewChat}
				>
					<EditPencil className="size-3.5" />
					<div class="flex items-center">{$i18n.t('New Chat')}</div>
				</button>
			{/if}

			{#if !isProject}
				<button
					type="button"
					class="flex h-[1.6875rem] w-full items-center gap-2 rounded-xl px-2 text-[0.8125rem] select-none cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-900"
					on:click={onCreateSubFolder}
				>
					<FolderIcon className="size-3.5" />
					<div class="flex items-center">{$i18n.t('Create Folder')}</div>
				</button>
			{/if}
			<hr class="border-gray-50/30 dark:border-gray-800/30 mx-1 my-0.5" />

			<button
				class="flex h-[1.6875rem] w-full items-center gap-2 rounded-xl px-2 text-[0.8125rem] select-none cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-900"
				on:click={() => {
					onMarkAllRead();
				}}
			>
				<CheckIcon className="size-3.5" />
				<div class="flex items-center">{$i18n.t('Mark all as read')}</div>
			</button>

			<hr class="border-gray-50/30 dark:border-gray-800/30 mx-1 my-0.5" />

			<button
				class="flex h-[1.6875rem] w-full items-center gap-2 rounded-xl px-2 text-[0.8125rem] select-none cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-900"
				on:click={() => {
					onEdit();
				}}
			>
				<EditPencil className="size-3.5" />
				<div class="flex items-center">{isProject ? '编辑项目' : $i18n.t('Edit')}</div>
			</button>

			{#if $user?.role === 'admin' || ($user?.permissions?.chat?.export ?? true)}
				<button
					class="flex h-[1.6875rem] w-full items-center gap-2 rounded-xl px-2 text-[0.8125rem] select-none cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-900"
					on:click={() => {
						onExport();
					}}
				>
					<Download className="size-3.5" />
					<div class="flex items-center">{$i18n.t('Export')}</div>
				</button>
			{/if}

			<hr class="border-gray-50/30 dark:border-gray-800/30 mx-1 my-0.5" />

			{#if isProject}
				<button
					type="button"
					class="flex h-[1.6875rem] w-full items-center gap-2 rounded-xl px-2 text-[0.8125rem] select-none cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-900"
					on:click={projectArchived ? onRestore : onArchive}
				>
					<ArchiveIcon className="size-3.5" />
					<div class="flex items-center">{projectArchived ? '恢复项目' : '归档项目'}</div>
				</button>
			{/if}
			{#if canDelete}
				<button
					type="button"
					class="flex h-[1.6875rem] w-full items-center gap-2 rounded-xl px-2 text-[0.8125rem] select-none cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-900"
					on:click={onDelete}
				>
					<TrashIcon className="size-3.5" />
					<div class="flex items-center">{isProject ? '删除项目' : $i18n.t('Delete')}</div>
				</button>
			{/if}
		</DropdownMenu>
	</div>
</Dropdown>
