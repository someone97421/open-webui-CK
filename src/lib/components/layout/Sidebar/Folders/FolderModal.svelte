<script lang="ts">
	import { getContext, createEventDispatcher, onMount, tick } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as I18n } from 'i18next';

	import Spinner from '$lib/components/common/Spinner.svelte';
	import Modal from '$lib/components/common/Modal.svelte';
	import AccessButton from '$lib/components/common/AccessButton.svelte';
	import FolderShareModal from './FolderShareModal.svelte';
	import XMark from '../icons/XMark.svelte';

	import { toast } from 'svelte-sonner';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { user, config, models, terminalServers } from '$lib/stores';
	import ModelSelector from '$lib/components/chat/ModelSelector/Selector.svelte';

	import Textarea from '$lib/components/common/Textarea.svelte';
	import Knowledge from '$lib/components/workspace/Models/Knowledge.svelte';
	import { getFolderById } from '$lib/apis/folders';
	import { getProjectAgents, updateProjectAgents } from '$lib/apis/terminal';
	import {
		getAccessibleProjectTerminals,
		getFolderProject,
		isProjectFolder
	} from '$lib/utils/projects';
	const i18n = getContext<Writable<I18n>>('i18n');

	export let show = false;
	export let onSubmit: Function = (e) => {};

	export let folderId = null;
	export let parentId = null;
	export let edit = false;
	export let project = false;

	let folder = null;
	let name = '';
	let meta = {
		background_image_url: null
	};
	let data: Record<string, any> = {
		description: '',
		model_ids: [] as string[],
		system_prompt: '',
		files: []
	};

	let loading = false;
	let initializing = false;
	let showAccessModal = false;
	let projectTerminalId = '';
	let agentsContent = '';
	let agentsSavedContent = '';
	let agentsLoading = false;
	let agentsLoadError = '';
	let agentsRequestSequence = 0;

	$: projectMode = project || isProjectFolder(folder);
	$: projectTerminals = getAccessibleProjectTerminals($terminalServers ?? []);
	$: agentsTooLarge = new TextEncoder().encode(agentsContent).length > 32 * 1024;
	$: if (show && projectMode && !projectTerminalId && projectTerminals.length > 0) {
		projectTerminalId = projectTerminals[0].id;
	}

	const loadAgents = async (id: string) => {
		const sequence = ++agentsRequestSequence;
		agentsLoading = true;
		agentsLoadError = '';
		try {
			const result = await getProjectAgents(localStorage.token, id);
			if (sequence !== agentsRequestSequence || folderId !== id) return;
			agentsContent = result.content;
			agentsSavedContent = result.content;
		} catch (error) {
			if (sequence !== agentsRequestSequence || folderId !== id) return;
			agentsLoadError = error instanceof Error ? error.message : String(error);
			toast.error(`AGENTS.md 加载失败：${agentsLoadError}`);
		} finally {
			if (sequence === agentsRequestSequence) agentsLoading = false;
		}
	};

	const submitHandler = async () => {
		if (initializing) return;
		loading = true;

		if ((data?.files ?? []).some((file) => file.status === 'uploading')) {
			toast.error($i18n.t('Please wait until all files are uploaded.'));
			loading = false;
			return;
		}

		const maxFileCount = $config?.features?.folder_max_file_count ?? '';
		if (maxFileCount && (data?.files ?? []).length > maxFileCount) {
			toast.error(
				$i18n.t('Maximum number of files per folder is {{max}}.', { max: maxFileCount ?? 0 })
			);
			loading = false;
			return;
		}

		if (projectMode && !projectTerminalId) {
			toast.error('请选择项目 Terminal');
			loading = false;
			return;
		}
		if (projectMode && edit && (agentsLoading || agentsTooLarge)) {
			toast.error(agentsTooLarge ? 'AGENTS.md 不能超过 32 KiB' : '请等待 AGENTS.md 加载完成');
			loading = false;
			return;
		}

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
		if (result === null || result === false) {
			loading = false;
			return;
		}

		if (projectMode && edit && agentsContent !== agentsSavedContent) {
			try {
				const saved = await updateProjectAgents(localStorage.token, folderId, agentsContent);
				agentsContent = saved.content;
				agentsSavedContent = saved.content;
				toast.success('AGENTS.md 已保存');
			} catch (error) {
				toast.error(
					`项目设置已保存，但 AGENTS.md 保存失败：${error instanceof Error ? error.message : String(error)}`
				);
				loading = false;
				return;
			}
		}

		show = false;
		loading = false;
	};

	const init = async () => {
		initializing = true;
		folder = null;
		projectTerminalId = '';
		agentsContent = '';
		agentsSavedContent = '';
		agentsLoadError = '';
		if (folderId) {
			folder = await getFolderById(localStorage.token, folderId).catch((error) => {
				toast.error(`${error}`);
				return null;
			});
			if (!folder) {
				initializing = false;
				return;
			}

			name = folder.name;
			meta = folder.meta || {
				background_image_url: null
			};
			data = {
				system_prompt: '',
				files: [],
				...folder.data,
				description: folder.data?.description ?? '',
				model_ids: folder.data?.model_ids ?? []
			};
			projectTerminalId = getFolderProject(folder)?.terminal_id ?? '';
			if (project || isProjectFolder(folder)) void loadAgents(folder.id);
		} else {
			projectTerminalId = projectTerminals[0]?.id ?? '';
		}

		focusInput();
		initializing = false;
	};

	const focusInput = async () => {
		await tick();
		const input = document.getElementById('folder-name') as HTMLInputElement;
		if (input) {
			input.focus();
			input.select();
		}
	};

	$: if (show) {
		init();
	}
	$: if (!show) showAccessModal = false;

	$: if (!show && !edit) {
		name = '';
		meta = {
			background_image_url: null
		};
		data = {
			description: '',
			model_ids: [],
			system_prompt: '',
			files: []
		};
		projectTerminalId = '';
		agentsContent = '';
		agentsSavedContent = '';
		agentsLoadError = '';
	}
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
					/>
				</div>

				{#if projectMode}
					<div class="my-2">
						<label for="project-terminal" class="mb-1 block text-xs text-gray-500">项目 Terminal</label>
						<select
							id="project-terminal"
							class="h-8 w-full rounded-lg border border-gray-100 bg-transparent px-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-gray-300 disabled:cursor-not-allowed disabled:opacity-50 dark:border-gray-800 dark:focus-visible:ring-gray-700"
							bind:value={projectTerminalId}
							disabled={loading || projectTerminals.length === 0}
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

					{#if edit}
						<div class="my-2">
							<div class="mb-1 flex items-center justify-between gap-2">
								<label for="project-agents" class="block text-xs text-gray-500" title="项目工作区中的 AGENTS.md">
									AGENTS.md
								</label>
								{#if agentsContent !== agentsSavedContent && !agentsLoading && !agentsLoadError}
									<span class="text-[0.6875rem] text-gray-400" role="status">未保存</span>
								{/if}
							</div>
							{#if agentsLoading}
								<div class="flex min-h-48 items-center justify-center rounded-lg border border-gray-100 dark:border-gray-800">
									<Spinner className="size-4" />
								</div>
							{:else if agentsLoadError}
								<div class="flex min-h-48 flex-col items-center justify-center gap-2 rounded-lg border border-gray-100 dark:border-gray-800" role="alert">
									<span class="text-xs text-gray-500">AGENTS.md 加载失败</span>
									<button type="button" class="rounded-lg px-2 py-1 text-xs hover:bg-gray-100 dark:hover:bg-gray-850" on:click={() => loadAgents(folderId)}>
										重试
									</button>
								</div>
							{:else}
								<textarea
									id="project-agents"
									class="block min-h-48 w-full resize-y rounded-lg border border-gray-100 bg-transparent px-2.5 py-2 font-mono text-xs leading-5 outline-none placeholder:text-gray-300 focus-visible:ring-2 focus-visible:ring-gray-300 dark:border-gray-800 dark:placeholder:text-gray-700 dark:focus-visible:ring-gray-700"
									bind:value={agentsContent}
									placeholder="输入项目指令…"
									spellcheck="false"
									disabled={loading || getFolderProject(folder)?.archived}
									title={getFolderProject(folder)?.archived ? '恢复项目后可编辑 AGENTS.md' : agentsTooLarge ? 'AGENTS.md 不能超过 32 KiB' : 'AGENTS.md'}
								></textarea>
							{/if}
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

					<div class="my-1 flex items-center justify-between gap-4">
						<label for="model-selector-folder-default-button" class="shrink-0 text-xs text-gray-500">
							{$i18n.t('Default Model')}
						</label>
						<div class="flex min-w-0 max-w-[65%] items-center gap-2">
							<div class="min-w-0">
								<ModelSelector
									id="folder-default"
									placeholder={$i18n.t('Use default')}
									items={$models.map((model) => ({ value: model.id, label: model.name, model }))}
									triggerClassName="text-xs"
									placement="auto"
									align="end"
									selectionOnly
									value={data.model_ids[0] ?? ''}
									bind:values={data.model_ids}
								/>
							</div>
							{#if data.model_ids.length}
								<button type="button" aria-label={$i18n.t('Reset')} class="shrink-0 px-0 py-1 text-gray-500 hover:text-gray-700 dark:hover:text-gray-200" on:click={() => (data.model_ids = [])}>
									<XMark className="size-3" />
								</button>
							{/if}
						</div>
					</div>

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
						disabled={loading || initializing || (projectMode && (!projectTerminalId || agentsLoading || agentsTooLarge))}
						title={projectMode && agentsTooLarge ? 'AGENTS.md 不能超过 32 KiB' : projectMode && !projectTerminalId ? '请选择项目 Terminal' : '保存'}
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
