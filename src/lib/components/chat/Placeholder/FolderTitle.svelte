<script lang="ts">
	import { getContext } from 'svelte';
	const i18n = getContext('i18n');

	import DOMPurify from 'dompurify';

	import fileSaver from 'file-saver';
	const { saveAs } = fileSaver;

	import { toast } from 'svelte-sonner';

	import { selectedFolder, chatId, user } from '$lib/stores';
	import { goto } from '$app/navigation';

	import {
		deleteFolderById,
		getFolderById,
		updateFolderById,
		createNewFolder
	} from '$lib/apis/folders';
	import { getChatsByFolderId } from '$lib/apis/chats';
	import { getFolderProject, isArchivedProject, isProjectFolder } from '$lib/utils/projects';

	import FolderModal from '$lib/components/layout/Sidebar/Folders/FolderModal.svelte';

	import Folder from '$lib/components/icons/Folder.svelte';
	import XMark from '$lib/components/icons/XMark.svelte';
	import FolderMenu from '$lib/components/layout/Sidebar/Folders/FolderMenu.svelte';
	import EllipsisHorizontal from '$lib/components/icons/EllipsisHorizontal.svelte';
	import DeleteConfirmDialog from '$lib/components/common/ConfirmDialog.svelte';
	import Emoji from '$lib/components/common/Emoji.svelte';
	import EmojiPicker from '$lib/components/common/EmojiPicker.svelte';

	export let folder = null;
	export let readOnly: boolean = false;

	export let onUpdate: Function = (folderId) => {};
	export let onDelete: Function = (folderId) => {};

	let showFolderModal = false;
	let showCreateSubFolderModal = false;
	let showDeleteConfirm = false;
	let showArchiveConfirm = false;
	let deleteFolderContents = true;
	$: isProject = isProjectFolder(folder);
	$: projectArchived = isArchivedProject(folder);

	const updateHandler = async ({ name, meta, data }) => {
		name = name?.trim();
		if (!name) {
			toast.error($i18n.t('Folder name cannot be empty.'));
			return null;
		}

		const currentName = folder.name;
		folder.name = name;
		const res = await updateFolderById(localStorage.token, folder.id, {
			name,
			...(meta ? { meta } : {}),
			...(data ? { data } : {})
		}).catch((error) => {
			toast.error(`${error}`);
			folder.name = currentName;
			return null;
		});
		if (!res) return null;

		folder.name = name;
		if (data) folder.data = data;
		toast.success($i18n.t('Folder updated successfully'));

		const latest = await getFolderById(localStorage.token, folder.id).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		const updatedFolder = { ...folder, ...res, ...latest };
		await selectedFolder.set(updatedFolder);
		onUpdate(updatedFolder);
		return updatedFolder;
	};

	const updateIconHandler = async (iconName) => {
		const res = await updateFolderById(localStorage.token, folder.id, {
			meta: {
				icon: iconName ?? ''
			}
		}).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		if (res) {
			folder.meta = { ...folder.meta, icon: iconName ?? '' };

			toast.success($i18n.t('Folder updated successfully'));

			const _folder = await getFolderById(localStorage.token, folder.id).catch((error) => {
				toast.error(`${error}`);
				return null;
			});

			const updatedFolder = { ...folder, ..._folder };
			await selectedFolder.set(updatedFolder);
			onUpdate(updatedFolder);
		}
	};

	const setProjectArchived = async (archived) => {
		const latest = await getFolderById(localStorage.token, folder.id).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		const project = getFolderProject(latest);
		if (!latest || !project) return null;
		const data = { ...latest.data, project: { ...project, archived } };
		const res = await updateFolderById(localStorage.token, folder.id, { data }).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		if (!res) return null;
		const updatedFolder = { ...latest, ...res, data };
		folder = updatedFolder;
		selectedFolder.set(updatedFolder);
		toast.success(archived ? '项目已归档，会话和文件已保留' : '项目已恢复');
		if (archived) onDelete(updatedFolder);
		else onUpdate(updatedFolder);
		return updatedFolder;
	};

	const deleteHandler = async () => {
		const deletedFolder = folder;
		const deletingProject = isProject;
		const res = await deleteFolderById(localStorage.token, deletedFolder.id, deletingProject || deleteFolderContents).catch(
			(error) => {
				toast.error(`${error}`);
				return null;
			}
		);

		if (res) {
			const wasSelectedProject = deletingProject && $selectedFolder?.id === deletedFolder.id;
			toast.success(deletingProject ? '项目、会话和工作区文件已删除' : $i18n.t('Folder deleted successfully'));
			onDelete(deletedFolder);
			if (wasSelectedProject) {
				selectedFolder.set(null);
				chatId.set('');
				goto('/');
			}
		}
	};

	const exportHandler = async () => {
		const chats = await getChatsByFolderId(localStorage.token, folder.id).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		if (!chats) {
			return;
		}

		const blob = new Blob([JSON.stringify(chats)], {
			type: 'application/json'
		});

		saveAs(blob, `folder-${folder.name}-export-${Date.now()}.json`);
	};

	const createSubFolderHandler = async ({ name, meta, data, parent_id }) => {
		name = name?.trim();
		if (!name) {
			toast.error($i18n.t('Folder name cannot be empty.'));
			return;
		}

		const res = await createNewFolder(localStorage.token, {
			name,
			data,
			meta,
			parent_id
		}).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		if (res) {
			toast.success($i18n.t('Folder created successfully'));
			onUpdate();
		}
	};
</script>

{#if folder}
	<FolderModal
		bind:show={showFolderModal}
		edit={true}
		folderId={folder.id}
		project={isProject}
		onSubmit={updateHandler}
	/>

	{#if !isProject}
		<FolderModal
			bind:show={showCreateSubFolderModal}
			parentId={folder.id}
			onSubmit={createSubFolderHandler}
		/>
	{/if}

	<DeleteConfirmDialog
		bind:show={showArchiveConfirm}
		title="归档项目？"
		confirmLabel="归档项目"
		on:confirm={() => setProjectArchived(true)}
	>
		<div class="text-sm text-gray-700 dark:text-gray-300">
			归档“{folder.name}”后，会话和文件都会保留，可随时恢复。
		</div>
	</DeleteConfirmDialog>

	<DeleteConfirmDialog
		bind:show={showDeleteConfirm}
		title={isProject ? '删除项目？' : $i18n.t('Delete folder?')}
		confirmLabel={isProject ? '删除项目' : $i18n.t('Delete')}
		on:confirm={deleteHandler}
	>
		<div class="mb-2 flex-1 text-sm text-gray-700 dark:text-gray-300">
			{isProject
				? `将永久删除“${folder.name}”、全部会话和 Terminal 工作区文件，无法撤销。`
				: $i18n.t(`Are you sure you want to delete "{{NAME}}"?`, { NAME: folder.name })}
		</div>

		{#if !isProject}
			<div class="flex items-center gap-1.5">
				<input
					aria-label={$i18n.t('Delete all contents inside this folder')}
					type="checkbox"
					bind:checked={deleteFolderContents}
				/>
				<div class="text-xs text-gray-500">
					{$i18n.t('Delete all contents inside this folder')}
				</div>
			</div>
		{/if}
	</DeleteConfirmDialog>

	<div
		class="{folder.data?.description
			? 'mb-0.5'
			: 'mb-2'} px-5 @md:max-w-3xl justify-between w-full flex relative group items-center"
	>
		<div class="text-center flex gap-3.5 items-center">
			{#if readOnly}
				<div
					class="rounded-full bg-gray-50/50 dark:bg-gray-800/40 size-11 flex justify-center items-center"
				>
					{#if folder?.meta?.icon}
						<Emoji className="size-7" shortCode={folder.meta.icon} />
					{:else}
						<Folder className="size-6" strokeWidth="2" />
					{/if}
				</div>
			{:else}
				<EmojiPicker
					onClose={() => {}}
					selected={folder?.meta?.icon ?? null}
					onSubmit={(name) => {
						console.log(name);
						updateIconHandler(name);
					}}
				>
					<button
						aria-label={$i18n.t('Change folder icon')}
						class="rounded-full bg-gray-50/50 dark:bg-gray-800/40 size-11 flex justify-center items-center outline-hidden focus:outline-hidden"
					>
						{#if folder?.meta?.icon}
							<Emoji className="size-7" shortCode={folder.meta.icon} />
						{:else}
							<Folder className="size-6" strokeWidth="2" />
						{/if}
					</button>
				</EmojiPicker>
			{/if}

			<div class="text-3xl line-clamp-1">
				{folder.name}
			</div>
		</div>

		{#if !readOnly || projectArchived}
			<div class="flex items-center translate-x-2.5">
				<FolderMenu
					align="end"
					{isProject}
					{projectArchived}
					canDelete={!isProject || folder?.user_id === $user?.id || $user?.role === 'admin'}
					onArchive={() => (showArchiveConfirm = true)}
					onRestore={() => setProjectArchived(false)}
					onEdit={() => {
						showFolderModal = true;
					}}
					onDelete={() => {
						showDeleteConfirm = true;
					}}
					onExport={() => {
						exportHandler();
					}}
					onCreateSubFolder={() => {
						showCreateSubFolderModal = true;
					}}
				>
					<div class="inline-flex p-1.5 dark:hover:bg-gray-850 rounded-full touch-auto">
						<EllipsisHorizontal className="size-4" strokeWidth="2.5" />
					</div>
				</FolderMenu>
			</div>
		{/if}
	</div>

	{#if folder.data?.description}
		<!-- Align with the title after the row padding, icon, and gap. -->
		<div
			class="mb-2 w-full pl-[4.875rem] pr-6 text-left text-sm text-gray-400 dark:text-gray-500 @md:max-w-3xl"
		>
			<p class="line-clamp-2 whitespace-pre-wrap break-words">{folder.data.description}</p>
		</div>
	{/if}
{/if}
