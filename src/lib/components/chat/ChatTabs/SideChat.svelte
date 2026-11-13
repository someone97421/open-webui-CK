<script lang="ts">
	import { getContext, setContext, onMount, tick } from 'svelte';
	import { writable, readable } from 'svelte/store';
	import { terminalSkills } from '$lib/stores';
	import { loadSkillCatalog } from '../skillCatalog';
	import { attachmentOverrides, freezeAttachmentDefaults, effectiveAttachments, updateAttachmentDelta, skillAvailable, toolAvailable, scopedSkills, defaultAttachmentPolicy, type AttachmentPolicy } from '$lib/utils/skillPolicy';
	import { runtimeAttachmentCapabilities } from '$lib/utils/skillPolicy';
	import { resolveToolApprovalMode } from '$lib/utils/toolPermissions';
	import { v4 as uuidv4 } from 'uuid';
	import {
		socket,
		user,
		openSideChatIds,
		tags,
		models,
		settings,
		config,
		toolServers,
		tools,
		skills,
		type Model
	} from '$lib/stores';
	import { createTemporaryChatId } from '$lib/utils/chatId';
	import { getTools } from '$lib/apis/tools';
	import { generateOpenAIChatCompletion, getErrorMessage } from '$lib/apis/openai';
	import { getTaskIdsByChatId, resumeTemporaryChat, stopTasksByChatId } from '$lib/apis';
	import {
		createNewChat,
		deleteChatById,
		getAllTags,
		getChatById,
		resolveChatMessageToolCall,
		updateChatById
	} from '$lib/apis/chats';
	import { refreshChatList, refreshFolderChatLists } from '$lib/stores/chatList';
	import {
		applyResponseStreamEvent,
		getPendingAskUserFromMessage
	} from '../Messages/structuredOutput';
	import Messages from '../Messages.svelte';
	import MessageInput from '../MessageInput.svelte';
	import FilesOverlay from '../MessageInput/FilesOverlay.svelte';
	import ConfirmDialog from '$lib/components/common/ConfirmDialog.svelte';
	import ElicitationDialog from '../ElicitationDialog.svelte';
	import {
		convertMessagesToHistory,
		createMessagesList,
		isRasterImageContentType
	} from '$lib/utils';

	export let initialPrompt = '';
	export let initialView: any = null;
	export const captureView = () => ({ draft, files, context, params, selectedModels, attachment_overrides,
		input_controls: { webSearchEnabled, imageGenerationEnabled, codeInterpreterEnabled, selectedFilterIds } });
	export let chatId = '';
	export let onChatUpdate: (chat: { id: string; title?: string }) => void = () => {};
	export let parentChatId = '';
	export let parentFolderId: string | null = null;
	export let history;
	export let modelId: string;
	export let systemPrompt = '';
	const i18n = getContext<any>('i18n');
	let dragged = false;
	const originalChatId = parentChatId;
	$: sideChatAllowed =
		$user?.role === 'admin' ||
		($user?.role === 'user' && ($user.permissions?.chat?.side_chat ?? false));
	// Snapshot the active branch once; later parent edits and streaming stay in the parent.
	const context = (() => {
		if (initialView?.context) return initialView.context;
		if (chatId) return [];
		const branch: any[] = [];
		let current = history?.currentId;
		const seen = new Set<string>();
		while (current && !seen.has(current) && history.messages[current]) {
			seen.add(current);
			const message = history.messages[current];
			branch.unshift(message);
			current = message.parentId;
		}
		while (branch.at(-1)?.role === 'assistant' && !branch.at(-1)?.done) branch.pop();
		return structuredClone(
			branch.map(
				(
					{ id, role, content, output, files, contextSummary, model, models, timestamp },
					index
				) => ({
					id,
					role,
					content: content ?? '',
					...(output?.length && role === 'assistant' ? { output } : {}),
					files,
					contextSummary,
					model,
					models,
					timestamp,
					done: true,
					parentId: branch[index - 1]?.id ?? null,
					childrenIds: branch[index + 1] ? [branch[index + 1].id] : []
				})
			)
		);
	})();
	const contextIds = new Set(context.map((message) => message.id));
	let loaded = !chatId;
	let isShared = false;
	let readOnly = false;
	let temporary =
		!chatId &&
		$user?.role !== 'admin' &&
		($user?.permissions?.chat?.temporary ?? true) &&
		($user?.permissions?.chat?.temporary_enforced ?? false);
	$: canUseTemporary = $user?.role === 'admin' || ($user?.permissions?.chat?.temporary ?? true);
	$: canSave =
		$user?.role === 'admin' ||
		!canUseTemporary ||
		!($user?.permissions?.chat?.temporary_enforced ?? false);
	$: canSend = loaded && !readOnly && sideChatAllowed && (temporary ? canUseTemporary : canSave);
	let selectedModels = initialView?.selectedModels ?? [modelId];
	let atSelectedModel: Model | undefined = undefined;
	$: sideModelId = atSelectedModel?.id ?? selectedModels[0];
	let files: any[] = initialView?.files ?? [];
	let params: Record<string, any> = { ...(initialView?.params ?? $settings.params) };
	let selectedToolIds: string[] = [];
	let selectedSkillIds: string[] = [];
	let attachment_overrides = attachmentOverrides(initialView?.attachment_overrides);
	let previousSkills: string[] = [];
	let previousTools: string[] = [];
	const attachmentPolicy = writable<AttachmentPolicy>(defaultAttachmentPolicy);
	setContext('attachmentPolicy', attachmentPolicy);
	setContext('chatMode', readable({ project: null, ready: true }));
	setContext('ensureChat', () => ensureSideChat());
	setContext('ensureTerminalChat', () => ensureSideChat());
	let workspaceChatId = '';
	let preparingWorkspace: Promise<string | null> | null = null;
	setContext('ensureWorkspaceChat', () => {
		if (preparingWorkspace) return preparingWorkspace;
		const owner = $user?.id;
		preparingWorkspace = (async () => {
			const sessionId = await ensureSideChat();
			if (!sessionId || disposed || $user?.id !== owner || id !== sessionId) return null;
			if (!temporary && !isShared && workspaceChatId !== sessionId) {
				await updateChatById(localStorage.token, sessionId, { workspace_has_files: true });
				if (disposed || $user?.id !== owner || id !== sessionId) return null;
				workspaceChatId = sessionId;
			}
			return sessionId;
		})().finally(() => { preparingWorkspace = null; });
		return preparingWorkspace;
	});
	$: sideModel = $models.find((model) => model.id === sideModelId);
	$: attachmentCaps = runtimeAttachmentCapabilities(sideModel ? [sideModel] : [], $config, $user, 'chat',
		{ web_search: webSearchEnabled, image_generation: imageGenerationEnabled, code_interpreter: codeInterpreterEnabled },
		params, !!$socket?.id);
	$: attachmentPolicy.set({ mode: 'chat', capabilities: attachmentCaps, terminalAvailable: false,
		skillSources: Object.fromEntries((sideModel?.info?.meta?.skillIds ?? []).map((id) => [id, '模型默认'])),
		toolSources: Object.fromEntries((sideModel?.info?.meta?.toolIds ?? []).map((id) => [id, '模型默认'])) });
	$: if (sideModel && loaded) {
		attachment_overrides = {
			...freezeAttachmentDefaults(attachment_overrides, sideModel.info?.meta?.skillIds ?? [], sideModel.info?.meta?.toolIds ?? ($settings as any)?.tools ?? []),
			skills: updateAttachmentDelta(attachment_overrides.skills, previousSkills, selectedSkillIds),
			tools: updateAttachmentDelta(attachment_overrides.tools, previousTools, selectedToolIds)
		};
		const catalog = scopedSkills($skills ?? [], $terminalSkills ?? []);
		previousSkills = effectiveAttachments(attachment_overrides.defaults!.skills, attachment_overrides.skills)
			.filter((id) => skillAvailable(catalog.find((skill) => skill.id === id), 'chat', attachmentCaps, false));
		previousTools = effectiveAttachments(attachment_overrides.defaults!.tools, attachment_overrides.tools)
			.filter((id) => toolAvailable(($tools ?? []).find((tool) => tool.id === id) ??
				(id.startsWith('direct_server:') && ($toolServers ?? []).some((server, index) => String(index) === id.slice('direct_server:'.length) || server.id === id.slice('direct_server:'.length)) ? { id } : null), attachmentCaps));
		selectedSkillIds = previousSkills;
		selectedToolIds = previousTools;
	}
	onMount(() => {
		if ($skills === null) void loadSkillCatalog(localStorage.token).then((result) => skills.set(result.items)).catch(() => {});
		if ($tools === null) void getTools(localStorage.token).then((items) => tools.set(items)).catch(() => {});
	});
	let selectedFilterIds: string[] = initialView?.input_controls?.selectedFilterIds ?? [];
	let webSearchEnabled = initialView?.input_controls?.webSearchEnabled ?? false;
	let imageGenerationEnabled = initialView?.input_controls?.imageGenerationEnabled ?? false;
	let codeInterpreterEnabled = initialView?.input_controls?.codeInterpreterEnabled ?? false;
	let defaultsInitialized = !!chatId || !!initialView?.input_controls;
	const applyModelDefaults = (selectedModelId: string) => {
		const selectedModel = $models.find((model) => model.id === selectedModelId);
		if (!selectedModel || defaultsInitialized) return;
		defaultsInitialized = true;
		const meta = selectedModel.info?.meta;
		const defaultFeature = (feature: 'web_search' | 'image_generation' | 'code_interpreter') =>
			!!meta?.defaultFeatureIds?.includes(feature) &&
			(meta?.capabilities?.[feature] ?? true) &&
			!!$config?.features?.[`enable_${feature}`] &&
			($user?.role === 'admin' || !!$user?.permissions?.features?.[feature]);
		selectedFilterIds = (meta?.defaultFilterIds ?? []).filter((filterId: string) =>
			selectedModel.filters?.some((filter: { id: string }) => filter.id === filterId)
		);
		webSearchEnabled = defaultFeature('web_search');
		imageGenerationEnabled = defaultFeature('image_generation');
		codeInterpreterEnabled = defaultFeature('code_interpreter');
	};
	$: if (!defaultsInitialized && sideModelId) applyModelDefaults(sideModelId);
	$: toolApprovalMode = resolveToolApprovalMode(
		params?.tool_approval_mode ?? $settings?.params?.tool_approval_mode,
		$config?.features?.enable_tool_permissions_auto ?? false
	);
	let interactions: { id: string; type: string; data: any; callback: (value: any) => void }[] = [];
	$: interaction = interactions[0];
	const resolveInteraction = (pending: typeof interaction, value: any) => {
		if (!interactions.includes(pending)) return;
		interactions = interactions.filter((item) => item !== pending);
		pending.callback(value);
	};
	const cancelInteractions = () => {
		for (const pending of interactions)
			resolveInteraction(pending, { status: 'cancelled', answers: {} });
	};
	$: askUser = {
		id: interaction?.id,
		show: interaction?.type === 'request:user_input',
		questions: interaction?.data?.questions ?? [],
		allowOther: interaction?.data?.allow_other ?? true,
		timeoutMs: interaction?.data?.timeout_ms ?? null,
		onConfirm: (value: any) => resolveInteraction(interaction, value),
		onCancel: () => resolveInteraction(interaction, { status: 'cancelled', answers: {} })
	};
	const resolvePendingAskUser = async (action: 'answer' | 'reject', answers?: unknown) => {
		const { message, call } = pendingAskUser;
		error = '';
		try {
			await resolveChatMessageToolCall(
				localStorage.token,
				id,
				message.id,
				call.call_id || call.id,
				action,
				{ answers }
			);
			// reconnect reads done to tell whether the resumed reply is still running
			message.done = false;
		} catch (err) {
			error = getErrorMessage(err);
		}
		void reconnect();
	};
	$: pendingAskUser =
		[...messages]
			.reverse()
			.filter((message) => (message.user_id ? message.user_id === $user?.id : !isShared))
			.map(getPendingAskUserFromMessage)
			.find(Boolean) ?? null;
	$: savedAskUserPrompt = pendingAskUser
		? {
				show: true,
				questions: Array.isArray(pendingAskUser.args?.questions)
					? pendingAskUser.args.questions
					: [],
				allowOther: pendingAskUser.args?.allow_other !== false,
				timeoutMs: null,
				onConfirm: (value: any) => void resolvePendingAskUser('answer', value?.answers ?? {}),
				onCancel: () => void resolvePendingAskUser('reject')
			}
		: null;
	let system = [
		systemPrompt,
		'This is a separate side conversation. Earlier messages are reference context only. Answer the side question; do not continue the parent task.'
	]
		.filter(Boolean)
		.join('\n\n');
	let id = chatId;
	let messages: any[] = [];
	let draft = initialView?.draft ?? '';
	let error = '';
	let busy = false;
	let sending = false;
	let recovering = false;
	let receivedDuringRecovery = new Set<string>();
	let disposed = false;
	let request: Promise<any> | null = null;
	let scroller: HTMLDivElement;
	let autoScroll = true;
	let input: MessageInput;
	const inputId = `side-chat-input-${uuidv4()}`;
	const messagesContainerId = `${inputId}-messages`;
	$: sideHistory = {
		currentId: messages.at(-1)?.id ?? null,
		messages: Object.fromEntries(
			messages.map((message, index) => [
				message.id,
				// The copied context belongs to saved history, outside this panel's visible branch.
				index === 0 ? { ...message, parentId: null } : message
			])
		)
	};
	const scroll = async () => {
		await tick();
		if (autoScroll) scroller?.scrollTo({ top: scroller.scrollHeight });
	};

	const receive = (event: any, callback?: (value: any) => void) => {
		if (!id || event.chat_id !== id) return;
		const { type, data } = event.data ?? {};
		if (recovering && event.message_id) receivedDuringRecovery.add(event.message_id);
		if (type === 'chat:title') {
			onChatUpdate({ id, title: data });
			void refreshChatList(localStorage.token);
			return;
		}
		if (type === 'chat:tags') {
			void getAllTags(localStorage.token).then((value) => tags.set(value));
			return;
		}
		if (type === 'context_compaction') {
			const checkpoint = [...context, ...messages].find(
				(message) => message.id === data.checkpoint_message_id
			);
			if (checkpoint && data.context_summary) checkpoint.contextSummary = data.context_summary;
			return;
		}
		if (type === 'request:interaction:done') {
			interactions = interactions.filter((item) => item.id !== data.interaction_id);
			return;
		}
		if (
			callback &&
			['request:user_input', 'request:elicitation', 'confirmation', 'input'].includes(type)
		) {
			if (!canSend) callback({ status: 'cancelled', answers: {} });
			else if (data?.tool_call && toolApprovalMode === 'full') callback(true);
			else
				interactions = [
					...interactions,
					{ id: data.interaction_id ?? uuidv4(), type, data, callback }
				];
			return;
		}
		const message = messages.find((m) => m.id === event.message_id);
		if (!message) return;
		if (type === 'response:completion')
			message.output = applyResponseStreamEvent(message.output, data);
		else if (type === 'chat:completion') {
			if (data.output) message.output = data.output;
			else if (data.content !== undefined) message.content = data.content;
			if (data.done) {
				message.done = true;
				busy = false;
				if (!temporary)
					$socket?.emit('events:chat', { chat_id: id, data: { type: 'last_read_at' } });
			}
		} else if (type === 'chat:message:error') {
			error = getErrorMessage(data.error);
			message.done = true;
			busy = false;
		} else if (type === 'status') {
			message.statusHistory = [...(message.statusHistory ?? []), data];
		} else if (type === 'source' || type === 'citation') {
			message.sources = [...(message.sources ?? []), data];
		} else if (type === 'chat:message:files' || type === 'files') {
			message.files = [...(message.files ?? []), ...data.files];
		} else if (type === 'chat:message' || type === 'replace') {
			message.content = data.content;
		} else if (type === 'chat:message:delta' || type === 'message') {
			message.content += data.content;
		} else if (type === 'chat:tasks:cancel') {
			cancelInteractions();
			if (data.output) message.output = data.output;
			message.done = true;
			busy = false;
		}
		messages = messages;
		void scroll();
	};

	const reconnect = async () => {
		if (!sideChatAllowed || (!temporary && !canSave) || !id || !$socket?.id || recovering) return;
		recovering = true;
		receivedDuringRecovery = new Set();
		try {
			if (!temporary) {
				const tasks = await getTaskIdsByChatId(localStorage.token, id);
				const saved = await getChatById(localStorage.token, id);
				if (disposed || !sideChatAllowed) return;
				isShared = saved.user_id !== $user?.id;
				workspaceChatId = saved.chat.workspace_has_files ? id : '';
				readOnly = isShared && saved.chat.share_mode !== 'continue';
				if (!loaded) {
					selectedModels = [saved.chat.models?.[0] ?? modelId];
					params = { ...saved.chat.params };
					attachment_overrides = attachmentOverrides(saved.chat.attachment_overrides);
					previousSkills = [];
					previousTools = [];
					selectedSkillIds = [];
					selectedToolIds = [];
					const controls = saved.chat.input_controls ?? {};
					webSearchEnabled = controls.webSearchEnabled ?? false;
					imageGenerationEnabled = controls.imageGenerationEnabled ?? false;
					codeInterpreterEnabled = controls.codeInterpreterEnabled ?? false;
					selectedFilterIds = controls.selectedFilterIds ?? [];
					system = params.system ?? saved.chat.system ?? $settings.system ?? '';
				}
				const savedHistory = saved.chat.history ?? convertMessagesToHistory(saved.chat.messages);
				messages = createMessagesList(
					savedHistory,
					saved.current_message_id ?? savedHistory.currentId
				)
					.filter((message) => !contextIds.has(message.id))
					.map((message) =>
						receivedDuringRecovery.has(message.id)
							? (messages.find((local) => local.id === message.id) ?? message)
							: message
					);
				busy = !!tasks.task_ids.length && messages.at(-1)?.done === false;
				if (!busy) messages = messages.map((message) => ({ ...message, done: true }));
				loaded = true;
				onChatUpdate({ id, title: saved.title });
				void scroll();
				return;
			}
			const result = await resumeTemporaryChat(localStorage.token, id, $socket.id);
			if (disposed || !canSend) return;
			for (const stream of result.streams) {
				const message = messages.find((m) => m.id === stream.message_id);
				if (message && !message.done) message.output = stream.output;
			}

			if (busy && !result.task_ids.length) {
				busy = false;
				error = $i18n.t('Connection lost. Please retry.');
				messages.forEach((m) => {
					m.done = true;
				});
			}
			messages = messages;
		} catch (err) {
			error = getErrorMessage(err);
			busy = false;
			messages = messages.map((message) => ({ ...message, done: true }));
		} finally {
			recovering = false;
		}
	};
	let creatingChat: Promise<string | null> | null = null;
	let createdHere = false;
	const ensureSideChat = async (): Promise<string | null> => {
		if (id) return id;
		if (!canSend || disposed || !sideModelId) return null;
		if (creatingChat) return creatingChat;
		creatingChat = (async () => {
			if (temporary) id = createTemporaryChatId($socket.id);
			else {
				const created = await createNewChat(localStorage.token, {
					title: draft.trim().slice(0, 100) || $i18n.t('New Chat'),
					...(originalChatId && { originalChatId, branchPointMessageId: context.at(-1)?.id ?? null }),
					models: [sideModelId], params: { ...params, system }, attachment_overrides,
					input_controls: { webSearchEnabled, imageGenerationEnabled, codeInterpreterEnabled, selectedFilterIds },
					history: convertMessagesToHistory(context), messages: context,
					files: context.flatMap((message) => message.files ?? []), tags: [], timestamp: Date.now()
				}, parentFolderId);
				if (!created?.id) throw new Error($i18n.t('Failed to create chat'));
				id = created.id;
				createdHere = true;
				if (disposed) {
					if (!draft.trim() && !files.length) void deleteChatById(localStorage.token, id, true).catch(() => {});
					return null;
				}
				onChatUpdate({ id, title: created.title });
				void refreshChatList(localStorage.token);
				if (created.folder_id) void refreshFolderChatLists(created.folder_id, created);
			}
			openSideChatIds.update((ids) => new Set([...ids, id]));
			return id;
		})().finally(() => { creatingChat = null; });
		return creatingChat;
	};
	const saveInputState = async () => {
		if (!id || temporary || isShared || !loaded) return;
		await updateChatById(localStorage.token, id, {
			params: { ...params, system }, models: [sideModelId], attachment_overrides,
			input_controls: { webSearchEnabled, imageGenerationEnabled, codeInterpreterEnabled, selectedFilterIds },
			files: [...context, ...messages].flatMap((message) => message.files ?? []).concat(files.filter((file) => file.status === 'uploaded'))
		});
	};
	let inputSaveTimer: ReturnType<typeof setTimeout> | undefined;
	let previousInputState = '';
	$: inputState = JSON.stringify({ params, sideModelId, attachment_overrides,
		selectedFilterIds, webSearchEnabled, imageGenerationEnabled, codeInterpreterEnabled });
	$: if (loaded && id && !temporary && !isShared && inputState !== previousInputState) {
		previousInputState = inputState;
		clearTimeout(inputSaveTimer);
		inputSaveTimer = setTimeout(() => {
			if (!disposed) void saveInputState().catch((err) => { error = getErrorMessage(err); });
		}, 250);
	}

	const send = async () => {
		if (!canSend || disposed) return;
		const question = draft.trim();
		if ((!question && !files.length) || busy || sending || recovering || pendingAskUser) return;
		if (!atSelectedModel && selectedModels.length !== 1) {
			error = $i18n.t('Select only one model');
			return;
		}
		if (files.some((file) => file.status === 'uploading' || file.status === 'error')) {
			error = $i18n.t('Please wait for files to finish uploading.');
			return;
		}
		if (!$socket?.connected || !sideModelId) {
			error = $i18n.t('Connect and select a model first.');
			return;
		}
		error = '';
		sending = true;
		try {
			if (!(await ensureSideChat())) return;
			await saveInputState();
			await tick();
			if (!canSend || disposed) return;
			if (!(await input?.uploadPendingFiles(id)) || busy || !canSend || disposed) return;
			const userMessage = {
				id: uuidv4(),
				parentId: messages.at(-1)?.id ?? (temporary ? null : (context.at(-1)?.id ?? null)),
				childrenIds: [] as string[],
				role: 'user',
				content: question,
				files: [...files],
				done: true,
				timestamp: Math.floor(Date.now() / 1000),
				models: [sideModelId]
			};
			const answer = {
				id: uuidv4(),
				parentId: userMessage.id,
				childrenIds: [] as string[],
				role: 'assistant',
				user_id: $user?.id,
				content: '',
				output: [],
				done: false,
				timestamp: Math.floor(Date.now() / 1000),
				model: sideModelId
			};
			userMessage.childrenIds.push(answer.id);
			if (messages.length) messages.at(-1).childrenIds.push(userMessage.id);
			const conversation = [...context, ...messages, userMessage].map((message) => {
				if (message.role === 'assistant' && message.output?.length)
					return {
						id: message.id,
						role: message.role,
						output: message.output,
						contextSummary: message.contextSummary
					};
				const images = (message.files ?? []).filter(
					(file: any) => file.type === 'image' || isRasterImageContentType(file.content_type)
				);
				return {
					id: message.id,
					role: message.role,
					contextSummary: message.contextSummary,
					content: images.length
						? [
								{ type: 'text', text: message.content ?? '' },
								...images.map((file: any) => ({ type: 'image_url', image_url: { url: file.url } }))
							]
						: message.content
				};
			});
			const requestFiles = [...context, ...messages, userMessage].flatMap(
				(message) => message.files ?? []
			);
			const directServers = selectedToolIds
				.filter((id) => id.startsWith('direct_server:'))
				.map((id) => id.slice('direct_server:'.length));
			messages = [...messages, userMessage, answer];
			draft = '';
			files = [];
			autoScroll = true;
			input?.setText('');
			busy = true;
			void scroll();
			request = generateOpenAIChatCompletion(localStorage.token, {
				model: sideModelId,
				model_item: $models.find((model) => model.id === sideModelId),
				stream: true,
				chat_id: id,
				session_id: $socket.id,
				id: answer.id,
				user_message: userMessage,
				...(!temporary &&
					!isShared && {
						parent_id: userMessage.parentId,
						background_tasks:
							messages.length === 2
								? {
										title_generation: $settings?.title?.auto ?? true,
										tags_generation: $settings?.autoTags ?? true
									}
								: {}
					}),
				params: { ...params, tool_approval_mode: toolApprovalMode },
				files: requestFiles,
				tool_ids: selectedToolIds.filter((id) => !id.startsWith('direct_server:')),
				skill_ids: selectedSkillIds,
				attachment_overrides,
				filter_ids: selectedFilterIds,
				terminal_id: undefined,
				tool_servers: $config?.features?.enable_tool_servers
					? [
							...($toolServers ?? []).filter(
								(server: any, index) =>
									directServers.includes(String(index)) || directServers.includes(server.id)
							),
						]
					: [],
				features: {
					web_search: webSearchEnabled,
					image_generation: imageGenerationEnabled,
					code_interpreter: codeInterpreterEnabled,
					memory: $settings.memory ?? $config?.features?.enable_memories ?? false
				},
				messages: [{ role: 'system', content: system }, ...(temporary ? conversation : [])]
			});
			const result = await request;
			if (result?.error) throw result.error;
		} catch (err) {
			error = getErrorMessage(err);
			if (busy && messages.at(-1)) messages.at(-1).done = true;
			busy = false;
			messages = messages;
		} finally {
			request = null;
			sending = false;
		}
	};

	const stop = async () => {
		cancelInteractions();
		await request?.catch(() => {});
		if (!id) return;
		try {
			await stopTasksByChatId(localStorage.token, id);
			busy = false;
			messages.forEach((m) => {
				m.done = true;
			});
			messages = messages;
		} catch (err) {
			if (!disposed) error = getErrorMessage(err);
		}
	};

	$: if (!canSend) {
		cancelInteractions();
		if (busy && !readOnly) void stop();
	}

	onMount(() => {
		const connection = $socket;
		connection?.on('events', receive);
		connection?.on('connect', reconnect);
		connection?.on('disconnect', cancelInteractions);
		if (id) {
			openSideChatIds.update((ids) => new Set([...ids, id]));
			void reconnect();
		}
		void tick().then(() => {
			if (disposed) return;
			if (initialView) input?.setText(draft);
			if (canSend && initialPrompt && !initialView) {
				draft = initialView?.draft ?? initialPrompt;
				input?.setText(draft);
				void send();
			}
			input?.focus();
		});
		return () => {
			disposed = true;
			clearTimeout(inputSaveTimer);
			connection?.off('events', receive);
			connection?.off('connect', reconnect);
			connection?.off('disconnect', cancelInteractions);
			cancelInteractions();
			if (id) {
				if (temporary) void stop();
				openSideChatIds.update((ids) => {
					const next = new Set(ids);
					next.delete(id);
					return next;
				});
				if (createdHere && !temporary && !draft.trim() && !files.length && !messages.length) {
					void deleteChatById(localStorage.token, id, true).then(() => refreshChatList(localStorage.token)).catch(() => {});
				} else if (!temporary) {
					void saveInputState().catch(() => {});
				}
			}
		};
	});
</script>

<div
	id={`${inputId}-pane`}
	class="relative flex h-full min-h-0 min-w-0 w-full flex-col @container overflow-hidden"
>
	<FilesOverlay show={dragged} />
	<div
		id={messagesContainerId}
		bind:this={scroller}
		class="flex-1 min-h-0 overflow-y-auto pb-2.5 scrollbar-hidden"
		on:scroll={() => {
			autoScroll = scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight < 50;
		}}
	>
		{#if messages.length}
			<Messages
				className="flex pt-4"
				chatId={id}
				history={sideHistory}
				selectedModels={[sideModelId]}
				prompt={draft}
				atSelectedModel={undefined}
				readOnly
				forkHandler={null}
				shareMode={null}
				sendMessage={() => {}}
				continueResponse={() => {}}
				regenerateResponse={() => {}}
				mergeResponses={() => {}}
				chatActionHandler={() => {}}
				allowDelete={false}
				allowToolApproval={canSend}
				onToolCallResolved={(res: { message_id: string }) => {
					// reconnect reads done to tell whether the resumed reply is still running
					const message = messages.find((m) => m.id === res.message_id);
					if (message) message.done = false;
					void reconnect();
				}}
				editCodeBlock={false}
				{autoScroll}
				{messagesContainerId}
			/>
		{:else if loaded}
			<div class="flex h-full items-center justify-center px-6">
				<div class="max-w-56 text-center">
					<p class="text-sm font-normal text-gray-600 dark:text-gray-300">
						{temporary ? $i18n.t('Temporary chat') : $i18n.t('New Chat')}
					</p>
					<p class="mt-1.5 text-xs leading-relaxed text-gray-400 dark:text-gray-500">
						{temporary
							? $i18n.t('Messages disappear when you close this tab.')
							: $i18n.t('Messages are saved to your chats.')}
					</p>
				</div>
			</div>
		{/if}
	</div>
	<div class="shrink-0 pb-2 z-10">
		{#if error}<p role="alert" class="px-4 py-2 text-xs text-gray-500 dark:text-gray-400">
				{error}
			</p>{/if}
		{#if canSend}
			<MessageInput
				bind:this={input}
				bind:dragged
				bind:prompt={draft}
				bind:autoScroll
				chatId={id}
				history={sideHistory}
				bind:selectedModels
				multipleModels={false}
				bind:atSelectedModel
				bind:files
				bind:params
				bind:selectedToolIds
				bind:selectedSkillIds
				bind:selectedFilterIds
				bind:webSearchEnabled
				bind:imageGenerationEnabled
				bind:codeInterpreterEnabled
				onUpdate={() => void saveInputState().catch((err) => { error = getErrorMessage(err); })}
				{toolApprovalMode}
				onToolApprovalModeChange={(mode: string) => {
					params = { ...params, tool_approval_mode: mode };
				}}
				askUser={savedAskUserPrompt ?? askUser}
				dropzoneId={`${inputId}-pane`}
				{inputId}
				{messagesContainerId}
				{temporary}
				onTemporaryChange={(value) => {
					if (!id && !sending) temporary = value;
				}}
				embedded
				callEnabled={false}
				terminalSelectionEnabled={false}
				generating={busy}
				stopResponse={stop}
				createMessagePair={() => {}}
				on:submit={() => void send()}
			/>
		{:else if loaded}
			<p role="status" class="px-4 py-2 text-xs text-gray-500">
				{$i18n.t('You do not have permission to use side chat.')}
			</p>
		{/if}
	</div>
</div>

{#if interaction}
	{#key interaction.id}
		{@const pending = interaction}
		{#if pending.type === 'request:elicitation'}
			<ElicitationDialog
				data={pending.data}
				onResponse={(value) => resolveInteraction(pending, value)}
			/>
		{:else if pending.type === 'confirmation' || pending.type === 'input'}
			<ConfirmDialog
				show={true}
				title={pending.data.title ?? $i18n.t('Tool Permissions')}
				message={pending.data.message ?? ''}
				input={pending.type === 'input'}
				inputPlaceholder={pending.data.placeholder ?? ''}
				inputValue={pending.data.value ?? ''}
				inputType={pending.data.input?.type ?? ''}
				inputOptions={pending.data.input?.options ?? []}
				on:confirm={(event) =>
					resolveInteraction(pending, pending.type === 'input' ? event.detail : true)}
				on:cancel={() => resolveInteraction(pending, false)}
			>
				{#if pending.data.tool_call}
					<div class="text-sm text-gray-500">
						<div class="font-medium break-all">{pending.data.tool_call.name}</div>
						<pre class="mt-2 max-h-64 overflow-auto whitespace-pre-wrap break-all">{JSON.stringify(
								pending.data.tool_call.arguments,
								null,
								2
							)}</pre>
					</div>
				{/if}
			</ConfirmDialog>
		{/if}
	{/key}
{/if}
