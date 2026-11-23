<script lang="ts">
	import { getContext } from 'svelte';
	const i18n = getContext('i18n');

	import fileSaver from 'file-saver';
	const { saveAs } = fileSaver;

	import { toast } from 'svelte-sonner';

	import { selectedFolder, chatId, user } from '$lib/stores';
	import { goto } from '$app/navigation';
	import {
		loadFolderDetails,
		updateFolderDetails,
		removeFolderState,
		type FolderDetails
	} from '$lib/stores/folderStates';

	import {
		deleteFolderById,
		updateFolderById,
		createNewFolder,
		markFolderChatsReadById
	} from '$lib/apis/folders';
	import { getChatsByFolderId } from '$lib/apis/chats';
	import { getFolderProject, isArchivedProject, isProjectFolder } from '$lib/utils/projects';
	import { refreshSidebar } from '$lib/stores/chatList';

	import FolderModal from '$lib/components/layout/Sidebar/Folders/FolderModal.svelte';
	import FolderShareModal from '$lib/components/layout/Sidebar/Folders/FolderShareModal.svelte';

	import FolderMenu from '$lib/components/layout/Sidebar/Folders/FolderMenu.svelte';
	import EllipsisHorizontal from '$lib/components/icons/EllipsisHorizontal.svelte';
	import DeleteConfirmDialog from '$lib/components/common/ConfirmDialog.svelte';

	export let folder: FolderDetails | null = null;
	export let readOnly: boolean = false;
	export let onNewChat: () => void = () => {};
	export let folderTabActions: import('svelte').Snippet | undefined = undefined;
	$: folderTabActions = renderFolderActions;

	export let onUpdate: Function = (folderId) => {};
	export let onDelete: Function = (folderId) => {};

	export let showFolderModal = false;
	let showCreateSubFolderModal = false;
	let showShareModal = false;
	let showDeleteConfirm = false;
	let showArchiveConfirm = false;
	let deleteFolderContents = true;
	$: isProject = isProjectFolder(folder);
	$: projectArchived = isArchivedProject(folder);

	const updateHandler = async ({ name, meta, data }) => {
		const targetFolder = folder;
		if (!targetFolder) return;
		name = name?.trim();
		if (!name) {
			toast.error($i18n.t('Folder name cannot be empty.'));
			return null;
		}

		const currentName = targetFolder.name;

		targetFolder.name = name;

		const res = await updateFolderById(localStorage.token, targetFolder.id, {
			name,
			...(meta ? { meta } : {}),
			...(data ? { data } : {})
		}).catch((error) => {
			toast.error(`${error}`);

			targetFolder.name = currentName;
			return null;
		});
		if (!res) return null;

		updateFolderDetails(targetFolder.id, res);
		toast.success($i18n.t('Folder updated successfully'));
		const latest = await loadFolderDetails(localStorage.token, targetFolder.id, true).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		const updatedFolder = { ...targetFolder, ...res, ...latest };
		if ($selectedFolder?.id === targetFolder.id) selectedFolder.set(updatedFolder);
		onUpdate(updatedFolder);
		return updatedFolder;
	};

	const setProjectArchived = async (archived: boolean) => {
		const targetFolder = folder;
		if (!targetFolder) return null;
		const latest = await loadFolderDetails(localStorage.token, targetFolder.id, true).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		const project = getFolderProject(latest);
		if (!latest || !project) return null;
		const data = { ...latest.data, project: { ...project, archived } };
		const res = await updateFolderById(localStorage.token, targetFolder.id, { data }).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		if (!res) return null;
		const updatedFolder = { ...latest, ...res, data };
		updateFolderDetails(targetFolder.id, updatedFolder);
		if (folder?.id === targetFolder.id) folder = updatedFolder;
		if ($selectedFolder?.id === targetFolder.id) selectedFolder.set(updatedFolder);
		toast.success(archived ? '项目已归档，会话和文件已保留' : '项目已恢复');
		if (archived) onDelete(updatedFolder);
		else onUpdate(updatedFolder);
		return updatedFolder;
	};

	const deleteHandler = async () => {
		const deletedFolder = folder;
		if (!deletedFolder) return;
		const deletingProject = isProject;
		const res = await deleteFolderById(localStorage.token, deletedFolder.id, deletingProject || deleteFolderContents).catch(
			(error) => {
				toast.error(`${error}`);
				return null;
			}
		);

		if (res) {
			removeFolderState(deletedFolder.id);
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

	const markAllReadHandler = async () => {
		if (!folder) return;
		const res = await markFolderChatsReadById(localStorage.token, folder.id).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		if (!res) return;

		await refreshSidebar(localStorage.token);
	};

	const exportHandler = async () => {
		if (!folder) return;
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
		return res;
	};
</script>

{#snippet renderFolderActions()}
	{#if folder && (!readOnly || (isProject && projectArchived && (folder.user_id === $user?.id || $user?.role === 'admin')))}
		<div class="flex shrink-0 items-center">
			<FolderMenu
				align="end"
				{onNewChat}
				{isProject}
				{projectArchived}
				canDelete={!isProject || folder.user_id === $user?.id || $user?.role === 'admin'}
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
				onMarkAllRead={markAllReadHandler}
				onCreateSubFolder={() => {
					showCreateSubFolderModal = true;
				}}
				onShare={!isProject && ($user?.role === 'admin' ||
				(folder?.user_id === $user?.id && $user?.permissions?.sharing?.folders))
					? () => (showShareModal = true)
					: null}
			>
				<div
					class="flex size-4 items-center justify-center rounded text-gray-400 hover:bg-gray-200 hover:text-gray-700 dark:hover:bg-white/10 dark:hover:text-white"
				>
					<EllipsisHorizontal className="size-3" strokeWidth="1.5" />
				</div>
			</FolderMenu>
		</div>
	{/if}
{/snippet}

{#if folder}
	<FolderModal
		bind:show={showFolderModal}
		edit={true}
		folderId={folder.id}
		project={isProject}
		onSubmit={updateHandler}
	/>

	{#if !isProject}
		<FolderShareModal bind:show={showShareModal} {folder} />
	{/if}

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
{/if}
