<script lang="ts">
	import { getContext, createEventDispatcher } from 'svelte';
	const i18n = getContext('i18n');
	const dispatch = createEventDispatcher();

	import RecursiveFolder from './RecursiveFolder.svelte';

	export let folderRegistry = {};

	export let folders = {};
	export let shiftKey = false;
	export let open = true;

	const PAGE_SIZE = 5;
	let visibleCount = PAGE_SIZE;
	$: if (!open) visibleCount = PAGE_SIZE;

	export let onDelete = () => {};
	export let onFolderUnreadCounts = () => {};

	let ownedList = [];
	let sharedList = [];

	$: {
		const rootKeys = Object.keys(folders)
			.filter((key) => {
				const f = folders[key];
				if (!f.name) return false;
				// Root folder: no parent, or shared folder whose parent isn't in our folders
				if (f.shared) {
					return !f.parent_id || !folders[f.parent_id];
				}
				return f.parent_id === null;
			})
			.sort((a, b) =>
				(folders[a].name ?? '').localeCompare(folders[b].name ?? '', undefined, {
					numeric: true,
					sensitivity: 'base'
				})
			);
		ownedList = rootKeys.filter((key) => !folders[key].shared);
		sharedList = rootKeys.filter((key) => folders[key].shared);
	}

	$: visibleOwnedList = ownedList.slice(0, visibleCount);
	$: visibleSharedList = sharedList.slice(0, Math.max(0, visibleCount - ownedList.length));
	$: if (open) {
		const newFolderIndex = [...ownedList, ...sharedList].findIndex((id) => folders[id]?.new);
		if (newFolderIndex >= visibleCount) {
			visibleCount = Math.ceil((newFolderIndex + 1) / PAGE_SIZE) * PAGE_SIZE;
		}
	}

	const onItemMove = (e) => {
		if (e.originFolderId) {
			folderRegistry[e.originFolderId]?.setFolderItems();
		}
	};
</script>

{#if ownedList.length > 0}
	<div role="list">
		{#each visibleOwnedList as folderId (folderId)}
			<RecursiveFolder
				className=""
				bind:folderRegistry
				{folders}
				{folderId}
				{shiftKey}
				{onDelete}
				{onItemMove}
				{onFolderUnreadCounts}
				on:import={(e) => {
					dispatch('import', e.detail);
				}}
				on:update={(e) => {
					dispatch('update', e.detail);
				}}
				on:change={(e) => {
					dispatch('change', e.detail);
				}}
			/>
		{/each}
	</div>
{/if}

{#if visibleSharedList.length > 0}
	<div class="w-full pl-2.5 text-[0.6875rem] text-gray-400 dark:text-gray-600 pt-2 pb-0.5">
		{$i18n.t('Shared')}
	</div>
	<div role="list">
		{#each visibleSharedList as folderId (folderId)}
			<RecursiveFolder
				className=""
				bind:folderRegistry
				{folders}
				{folderId}
				{shiftKey}
				{onDelete}
				{onItemMove}
				{onFolderUnreadCounts}
				on:import={(e) => {
					dispatch('import', e.detail);
				}}
				on:update={(e) => {
					dispatch('update', e.detail);
				}}
				on:change={(e) => {
					dispatch('change', e.detail);
				}}
			/>
		{/each}
	</div>
{/if}

{#if ownedList.length + sharedList.length > visibleCount}
	<button
		type="button"
		class="w-full px-2.5 py-1.5 text-left text-xs text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
		on:click={() => (visibleCount += PAGE_SIZE)}
	>
		{$i18n.t('Click to show more')}
	</button>
{/if}
