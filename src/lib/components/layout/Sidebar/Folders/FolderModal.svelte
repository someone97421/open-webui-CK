<script lang="ts">
	import { getContext, onDestroy, tick } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as I18n } from 'i18next';

	import Spinner from '$lib/components/common/Spinner.svelte';
	import Modal from '$lib/components/common/Modal.svelte';
	import AccessButton from '$lib/components/common/AccessButton.svelte';
	import FolderShareModal from './FolderShareModal.svelte';
	import XMark from '../icons/XMark.svelte';

	import { toast } from 'svelte-sonner';
	import { user, config, models, terminalServers } from '$lib/stores';
	import ModelSelector from '$lib/components/chat/ModelSelector/Selector.svelte';
	import ProjectAgentsEditor from '$lib/components/chat/Placeholder/ProjectAgentsEditor.svelte';
	import FolderAttachmentDefaults from '$lib/components/chat/FolderAttachmentDefaults.svelte';
	import Textarea from '$lib/components/common/Textarea.svelte';
	import Collapsible from '$lib/components/common/Collapsible.svelte';
	import AdvancedParams from '$lib/components/chat/Settings/Advanced/AdvancedParams.svelte';
	import Knowledge from '$lib/components/workspace/Models/Knowledge.svelte';
	import { getFolderById } from '$lib/apis/folders';
	import {
		getAccessibleProjectTerminals,
		getFolderProject,
		isProjectFolder
	} from '$lib/utils/projects';
	const i18n = getContext<Writable<I18n>>('i18n');

	export let show = false;
	export let onSubmit: Function = (e) => {};
	export let folderId: string | null = null;
	export let parentId = null;
	export let edit = false;
	export let project = false;

	let folder = null;
	let name = '';
	let meta = { background_image_url: null };
	let data: Record<string, any> = {
		description: '',
		model_ids: [] as string[],
		params: {} as Record<string, any>,
		skill_ids: [] as string[],
		tool_ids: [] as string[],
		system_prompt: '',
		files: []
	};

	let loading = false;
	let initializing = false;
	let attachmentsLoading = true;
	let attachmentsLoadFailed = false;
	let showAccessModal = false;
	let projectTerminalId = '';
	let paramsExpanded = false;
	let agentsExpanded = false;
	let agentsOpened = false;
	let agentsEditor: ProjectAgentsEditor | undefined;
	let agentsSaving = false;
	let agentsSaveBlocked = false;
	let modalSequence = 0;

	$: projectMode = project || isProjectFolder(folder);
	$: projectArchived = projectMode && (getFolderProject(folder)?.archived ?? false);
	$: agentsTerminalChanged = projectMode && !!folder && projectTerminalId !== getFolderProject(folder)?.terminal_id;
	$: projectTerminals = getAccessibleProjectTerminals($terminalServers ?? []);
	$: if (show && projectMode && !projectArchived && !projectTerminalId && projectTerminals.length > 0) {
		projectTerminalId = projectTerminals[0].id;
	}

	const isCurrent = (sequence: number, id: string | null) =>
		show && sequence === modalSequence && folderId === id;

	const submitHandler = async () => {
		if (initializing || loading || attachmentsLoading || attachmentsLoadFailed || agentsSaving || projectArchived || (folderId && !folder)) return;
		if ((data?.files ?? []).some((file) => file.status === 'uploading')) {
			toast.error($i18n.t('Please wait until all files are uploaded.'));
			return;
		}
		const maxFileCount = $config?.features?.folder_max_file_count ?? '';
		if (maxFileCount && (data?.files ?? []).length > maxFileCount) {
			toast.error($i18n.t('Maximum number of files per folder is {{max}}.', { max: maxFileCount ?? 0 }));
			return;
		}
		if (projectMode && !projectTerminalId) {
			toast.error('请选择项目 Terminal');
			return;
		}
		if (agentsSaveBlocked && !agentsTerminalChanged) {
			toast.error('AGENTS.md 不能超过 32 KiB');
			return;
		}

		const sequence = modalSequence;
		const id = folderId;
		const editor = agentsTerminalChanged ? undefined : agentsEditor;
		loading = true;
		try {
			const result = await onSubmit({
				name,
				meta,
				data: {
					...data,
					description: data.description.trim(),
					model_ids: data.model_ids,
					system_prompt: data.system_prompt,
					files: data.files,
					...(projectMode
						? {
								project: {
									version: 1,
									terminal_id: projectTerminalId,
									archived: getFolderProject(folder)?.archived ?? false
								}
							}
						: {})
				},
				parent_id: edit ? undefined : parentId
			});
			if (!isCurrent(sequence, id) || result === null || result === false) return;
			if (editor && !(await editor.save())) {
				if (isCurrent(sequence, id)) toast.error('项目设置已保存，AGENTS.md 未保存');
				return;
			}
			if (isCurrent(sequence, id)) show = false;
		} catch (error) {
			if (isCurrent(sequence, id)) toast.error(`${error}`);
		} finally {
			if (sequence === modalSequence) loading = false;
		}
	};

	const init = async (isOpen: boolean, id: string | null) => {
		const sequence = ++modalSequence;
		initializing = isOpen;
		loading = false;
		attachmentsLoading = isOpen;
		attachmentsLoadFailed = false;
		showAccessModal = false;
		folder = null;
		name = '';
		meta = { background_image_url: null };
		data = { description: '', model_ids: [], params: {}, skill_ids: [], tool_ids: [], system_prompt: '', files: [] };
		paramsExpanded = false;
		projectTerminalId = '';
		agentsExpanded = false;
		agentsOpened = false;
		agentsSaving = false;
		agentsSaveBlocked = false;
		if (!isOpen) return;
		if (id) {
			const loaded = await getFolderById(localStorage.token, id).catch((error) => {
				if (isCurrent(sequence, id)) toast.error(`${error}`);
				return null;
			});
			if (!isCurrent(sequence, id)) return;
			if (!loaded) {
				initializing = false;
				return;
			}
			folder = loaded;
			name = folder.name;
			meta = folder.meta || { background_image_url: null };
			data = {
				system_prompt: '',
				files: [],
				...folder.data,
				description: folder.data?.description ?? '',
				model_ids: folder.data?.model_ids ?? [],
				params: structuredClone(folder.data?.params ?? {}),
				skill_ids: folder.data?.skill_ids ?? null,
				tool_ids: folder.data?.tool_ids ?? null
			};
			projectTerminalId = getFolderProject(folder)?.terminal_id ?? '';
		} else {
			projectTerminalId = projectTerminals[0]?.id ?? '';
		}
		initializing = false;
		await tick();
		if (!isCurrent(sequence, id)) return;
		const input = document.getElementById('folder-name') as HTMLInputElement;
		input?.focus();
		input?.select();
	};

	$: void init(show, folderId);

	onDestroy(() => {
		modalSequence += 1;
	});
</script>

<Modal
	ariaLabel={projectMode ? (edit ? '项目设置' : '新建项目') : edit ? $i18n.t('Edit Folder') : $i18n.t('Create Folder')}
	size="md"
	bind:show
>
	<div>
		<div class="flex justify-between px-4 pb-1 pt-3 dark:text-gray-300">
			<div class="self-center text-sm">
				{projectMode ? (edit ? '项目设置' : '新建项目') : edit ? $i18n.t('Edit Folder') : $i18n.t('Create Folder')}
			</div>
			<div class="flex items-center gap-1">
				{#if !projectMode && edit && folder && ($user?.role === 'admin' || (folder.user_id === $user?.id && $user?.permissions?.sharing?.folders))}
					<AccessButton disabled={loading} on:click={() => (showAccessModal = true)} />
				{/if}
				<button
					type="button"
					aria-label={$i18n.t('Close')}
					class="self-center rounded-lg px-0 py-1 text-gray-500 transition hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
					on:click={() => (show = false)}
				>
					<XMark className="size-4" />
				</button>
			</div>
		</div>

		<div class="flex w-full flex-col px-4 pb-4 dark:text-gray-200 md:flex-row">
			<form class="flex w-full flex-col" on:submit|preventDefault={submitHandler}>
				<div class="mt-1 flex w-full flex-col">
					<label for="folder-name" class="mb-1 block text-xs text-gray-500">
						{projectMode ? '项目名称' : $i18n.t('Folder Name')}
					</label>
					<input
						id="folder-name"
						class="w-full bg-transparent text-sm outline-hidden placeholder:text-gray-300 dark:placeholder:text-gray-700"
						type="text"
						bind:value={name}
						placeholder={projectMode ? '输入项目名称' : $i18n.t('Enter folder name')}
						autocomplete="off"
						disabled={loading || initializing || projectArchived}
					/>
				</div>

				<div class="my-2">
					<label for="folder-description" class="mb-1 block text-xs text-gray-500">
						{$i18n.t('Description')}
					</label>
					<Textarea
						id="folder-description"
						ariaLabel={$i18n.t('Description')}
						className="w-full text-sm bg-transparent placeholder:text-gray-300 dark:placeholder:text-gray-700 outline-hidden"
						placeholder={$i18n.t('Enter description')}
						maxSize={200}
						bind:value={data.description}
						disabled={loading || initializing || projectArchived}
					/>
				</div>

				<div class="my-2 flex items-center justify-between gap-4">
					<label for="model-selector-folder-default-button" class="shrink-0 text-xs text-gray-500" title="仅影响新会话，会话中可自由切换模型；清空后使用常规默认模型。">
						{$i18n.t('Default Model')}
					</label>
					<div class="flex min-w-0 max-w-[65%] items-center gap-2">
						<div class="min-w-0">
							<ModelSelector
								id="folder-default"
								placeholder={$i18n.t('Use default')}
								items={$models.filter((model) => !projectMode || model.info?.meta?.capabilities?.terminal !== false).map((model) => ({ value: model.id, label: model.name, model }))}
								triggerClassName="text-xs"
								placement="auto"
								align="end"
								selectionOnly
								disabled={loading || initializing || projectArchived}
								value={data.model_ids[0] ?? ''}
								bind:values={data.model_ids}
							/>
						</div>
						{#if data.model_ids.length}
							<button type="button" aria-label={$i18n.t('Reset')} title="清空后使用常规默认模型" disabled={loading || initializing || projectArchived} class="shrink-0 rounded px-0 py-1 text-gray-500 hover:text-gray-700 focus-visible:outline focus-visible:outline-2 disabled:opacity-50 dark:hover:text-gray-200" on:click={() => (data.model_ids = [])}>
								<XMark className="size-3" />
							</button>
						{/if}
					</div>
				</div>

				{#if $user?.role === 'admin' || ($user?.permissions?.chat?.params ?? true)}
					<fieldset
						class="my-2 min-w-0 disabled:opacity-50"
						aria-label="默认模型参数"
						title="仅用于新会话初始化，会话中可自行调整模型参数。"
						disabled={initializing || attachmentsLoading || loading || agentsSaving || projectArchived}
					>
						<Collapsible
							title="默认模型参数"
							buttonClassName="w-full rounded py-1 text-xs text-gray-500 hover:text-gray-700 focus-visible:outline focus-visible:outline-2 dark:hover:text-gray-300"
							bind:open={paramsExpanded}
						>
							<div slot="content" class="mt-2 min-w-0">
								<AdvancedParams
									layout="grid"
									admin={$user?.role === 'admin'}
									custom={true}
									bind:params={data.params}
								/>
							</div>
						</Collapsible>
					</fieldset>
				{/if}

				{#if show && !initializing && (!folderId || folder)}
					<FolderAttachmentDefaults
						{folderId}
						parentId={folder?.parent_id ?? parentId}
						project={projectMode}
						terminalId={projectTerminalId}
						modelIds={data.model_ids}
						bind:skillIds={data.skill_ids}
						bind:toolIds={data.tool_ids}
						bind:loading={attachmentsLoading}
						bind:loadFailed={attachmentsLoadFailed}
						disabled={loading || projectArchived}
					/>
				{/if}

				{#if projectMode}
					<div class="my-2">
						<label for="project-terminal" class="mb-1 block text-xs text-gray-500">项目 Terminal</label>
						<select
							id="project-terminal"
							class="h-8 w-full rounded-lg border border-gray-100 bg-transparent px-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-gray-300 disabled:cursor-not-allowed disabled:opacity-50 dark:border-gray-800 dark:focus-visible:ring-gray-700"
							bind:value={projectTerminalId}
							disabled={!!folderId || loading || initializing || agentsSaving || projectArchived || projectTerminals.length === 0}
							required
							title="项目会话固定使用此 Terminal"
						>
							{#if projectTerminals.length === 0}
								<option value="">暂无可用 Terminal</option>
							{:else}
								{#each projectTerminals as terminal}
									<option value={terminal.id}>{terminal.name || terminal.id}</option>
								{/each}
							{/if}
						</select>
					</div>

					{#if edit && folder && !initializing}
						<div class="my-2">
							<button
								type="button"
								class="flex w-full items-center justify-between rounded-lg py-1 text-xs text-gray-500 hover:text-gray-800 dark:hover:text-gray-200"
								aria-expanded={agentsExpanded}
								aria-controls="project-advanced-settings"
								disabled={agentsTerminalChanged}
								title={agentsTerminalChanged ? '请先保存 Terminal 绑定，再编辑 AGENTS.md；旧连接的草稿不会写入新连接' : '编辑项目 AGENTS.md'}
								on:click={() => {
									agentsExpanded = !agentsExpanded;
									agentsOpened = true;
								}}
							>
								<span>高级设置</span>
								<span aria-hidden="true">{agentsExpanded ? '−' : '+'}</span>
							</button>
							<div id="project-advanced-settings" hidden={!agentsExpanded} class="mt-2">
								{#if agentsTerminalChanged}
									<div class="mb-2 text-xs text-gray-500" title="旧连接的 AGENTS.md 草稿不会写入新连接">请先保存 Terminal 绑定</div>
								{/if}
								<div hidden={agentsTerminalChanged}>
									{#if show && agentsOpened}
										<ProjectAgentsEditor
											bind:this={agentsEditor}
											projectId={folder.id}
											readOnly={projectArchived || agentsTerminalChanged}
											disabled={loading}
											bind:saving={agentsSaving}
											bind:saveBlocked={agentsSaveBlocked}
										/>
									{/if}
								</div>
							</div>
						</div>
					{/if}
				{:else}
					<input
						id="folder-background-image-input"
						type="file"
						hidden
						accept="image/*"
						on:change={(e) => {
							const inputFiles = e.target.files;
							const reader = new FileReader();
							reader.onload = (event) => {
								meta.background_image_url = `${event.target.result}`;
							};
							if (inputFiles?.length && ['image/gif', 'image/webp', 'image/jpeg', 'image/png'].includes(inputFiles[0].type)) {
								reader.readAsDataURL(inputFiles[0]);
							} else {
								e.target.value = '';
							}
						}}
					/>

					<div class="mt-1 flex w-full items-center justify-between">
						<div id="folder-background-image-label" class="text-xs text-gray-500">
							{$i18n.t('Folder Background Image')}
						</div>
						<button
							type="button"
							aria-labelledby="folder-background-image-label folder-background-image-state"
							class="flex rounded-sm p-1 px-3 text-xs transition"
							on:click={() => {
								if (meta?.background_image_url !== null) {
									meta.background_image_url = null;
								} else {
									document.getElementById('folder-background-image-input')?.click();
								}
							}}
						>
							<span class="ml-2 self-center" id="folder-background-image-state">
								{(meta?.background_image_url ?? null) === null ? $i18n.t('Upload') : $i18n.t('Reset')}
							</span>
						</button>
					</div>

					<hr class="my-2.5 w-full border-gray-50 dark:border-gray-850/30" />

					{#if $user?.role === 'admin' || ($user?.permissions.chat?.system_prompt ?? true)}
						<div class="my-1">
							<div class="mb-2 text-xs text-gray-500">{$i18n.t('System Prompt')}</div>
							<Textarea
								className="text-sm w-full bg-transparent outline-hidden"
								placeholder={$i18n.t('Write your model system prompt content here\ne.g.) You are Mario from Super Mario Bros, acting as an assistant.')}
								maxSize={200}
								bind:value={data.system_prompt}
							/>
						</div>
					{/if}

					<div class="my-2">
						<Knowledge bind:selectedItems={data.files}>
							<div slot="label">
								<div class="flex w-full justify-between">
									<div class="text-xs text-gray-500">{$i18n.t('Knowledge')}</div>
								</div>
							</div>
						</Knowledge>
					</div>
				{/if}

				<div class="flex justify-end gap-1.5 pt-3 text-sm font-normal">
					<button
						class="flex h-7 shrink-0 items-center justify-center gap-1.5 rounded-lg bg-gray-900 px-2.5 text-xs font-normal text-white transition hover:bg-black disabled:cursor-not-allowed disabled:opacity-60 dark:bg-gray-100 dark:text-gray-900 dark:hover:bg-white"
						type="submit"
						disabled={loading || initializing || attachmentsLoading || attachmentsLoadFailed || agentsSaving || (agentsSaveBlocked && !agentsTerminalChanged) || projectArchived || (!!folderId && !folder) || (projectMode && !projectTerminalId)}
						title={projectArchived ? '恢复项目后可编辑设置' : attachmentsLoading ? '正在加载默认配置' : attachmentsLoadFailed ? '请重新加载默认配置后保存' : agentsSaveBlocked && !agentsTerminalChanged ? 'AGENTS.md 不能超过 32 KiB' : projectMode && !projectTerminalId ? '请选择项目 Terminal' : '保存'}
					>
						{projectMode && !edit ? '创建项目' : $i18n.t('Save')}
						{#if loading}<Spinner className="size-3" />{/if}
					</button>
				</div>
			</form>
		</div>
	</div>
</Modal>

{#if show && !projectMode && edit && folder && ($user?.role === 'admin' || folder.user_id === $user?.id)}
	<FolderShareModal bind:show={showAccessModal} {folder} />
{/if}
