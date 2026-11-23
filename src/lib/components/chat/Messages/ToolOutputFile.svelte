<script lang="ts">
	import { resolveTerminalTarget } from '$lib/apis/terminal';
	// Keep keys in nested template expressions visible to i18next-parser.
	// $i18n.t("Terminal unavailable");
	// $i18n.t("No preview available");

	import { getContext, onDestroy } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import { toast } from 'svelte-sonner';
	import {
		selectedTerminalId,
		showTabs,
		showFileNavPath,
		terminalServers
	} from '$lib/stores';
	import { downloadFileBlob, downloadFilePreview, readFile } from '$lib/apis/terminal';
	import { getFileContentById } from '$lib/apis/files';
	import FilePreview from '$lib/components/chat/FileNav/FilePreview.svelte';
	import Icon from '$lib/components/chat/FileNav/Icon.svelte';
	import { fileIconName } from '$lib/components/chat/FileNav/fileIcon';
	import { normalizeDocumentTargetPage } from '$lib/utils/documentPreview';

	export let item: any;
	export let chatId = '';
	export let localBlob: Blob | null = null;
	export let attachment = false;
	export let modelId: string | null = null;

	const i18n = getContext<Writable<i18nType>>('i18n');

	let expanded = true;
	let loading = false;
	let loadedKey = '';
	let error = '';
	let objectUrls: string[] = [];
	let destroyed = false;
	let previewGeneration = 0;
	let observedPreviewKey = '';
	let expansionKey = '';

	let fileImageUrl: string | null = null;
	let fileVideoUrl: string | null = null;
	let fileAudioUrl: string | null = null;
	let filePdfData: ArrayBuffer | null = null;
	let fileSqliteData: ArrayBuffer | null = null;
	let fileModelData: ArrayBuffer | null = null;
	let fileDocxData: ArrayBuffer | null = null;
	let fileContent: string | null = null;
	let fileOfficeSlides: string[] | null = null;
	let currentSlide = 0;
	let selectedExcelSheet = '';
	let excelWorkbook: import('xlsx').WorkBook | null = null;

	const IMAGE_EXTS = new Set(['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'ico', 'avif']);
	const VIDEO_EXTS = new Set(['mp4', 'webm', 'mov', 'ogv', 'avi', 'mkv']);
	const AUDIO_EXTS = new Set(['mp3', 'wav', 'ogg', 'oga', 'flac', 'm4a', 'aac', 'wma', 'opus']);
	const SQLITE_EXTS = new Set(['db', 'sqlite', 'sqlite3', 'db3']);
	const OFFICE_EXTS = new Set(['docx', 'xlsx', 'xls', 'pptx']);

	$: effectiveChatId = chatId || String(item?.session_id ?? '');
	$: fileId =
		item?.source === 'open_webui'
			? (String(item.path ?? '').match(/^\/api\/v1\/files\/([^/]+)\/content$/)?.[1] ?? '')
			: '';
	// Content URLs have no extension; use the filename to select the preview.
	$: path = String(fileId ? item.name : item?.full_path || item?.path || '');
	$: name = String(item?.name || path.split('/').filter(Boolean).at(-1) || 'file');
	$: targetPage = normalizeDocumentTargetPage(item?.page);
	$: selector = item?.terminal_selector;
	$: terminal =
		selector
			? resolveTerminalTarget(selector, $terminalServers ?? [], localStorage.token, {
					chatId: effectiveChatId,
					modelId: item?.model_id ?? modelId
				})
			: null;
	$: unavailable = !terminal && !fileId && !localBlob;
	$: previewKey =
		localBlob ? `local:${path}:${effectiveChatId}` : fileId || (terminal ? `${terminal.baseUrl}|${terminal.key}|${terminal.context.modelId}|${path}|${effectiveChatId}` : '');

	$: previewClass = isImage(path)
		? 'h-[22rem]'
		: isPdf(path) ||
			  isOffice(path) ||
			  ['glb', 'gltf', 'stl', 'obj', 'ply'].includes(getExt(path)) ||
			  getExt(path) === 'html' ||
			  getExt(path) === 'htm' ||
			  getExt(path) === 'svg'
			? 'h-96'
			: 'h-72';
	$: nextExpansionKey = JSON.stringify([effectiveChatId, item?.source, selector, path, attachment, item?.display_mode]);
	$: if (nextExpansionKey !== expansionKey) {
		expansionKey = nextExpansionKey;
		expanded = !attachment || isImage(path) || item?.display_mode === 'inline' ||
			(item?.display_mode == null && item?.displayed === true);
	}
	$: if (previewKey !== observedPreviewKey) {
		observedPreviewKey = previewKey;
		previewGeneration += 1;
		loading = false;
		loadedKey = '';
		error = '';
		clearPreview();
	}
	$: if (expanded && !unavailable && path && previewKey !== loadedKey && !loading) {
		void loadPreview(previewKey);
	}

	const getExt = (value: string) => value.split('.').pop()?.toLowerCase() ?? '';
	const isImage = (value: string) => IMAGE_EXTS.has(getExt(value));
	const isVideo = (value: string) => VIDEO_EXTS.has(getExt(value));
	const isAudio = (value: string) => AUDIO_EXTS.has(getExt(value));
	const isSqlite = (value: string) => SQLITE_EXTS.has(getExt(value));
	const isPdf = (value: string) => getExt(value) === 'pdf';
	const isOffice = (value: string) => OFFICE_EXTS.has(getExt(value));

	const t = (key: string, vars?: Record<string, unknown>) => $i18n?.t?.(key, vars) ?? key;

	function clearPreview() {
		for (const url of objectUrls) URL.revokeObjectURL(url);
		objectUrls = [];
		fileImageUrl = null;
		fileVideoUrl = null;
		fileAudioUrl = null;
		filePdfData = null;
		fileSqliteData = null;
		fileModelData = null;
		fileDocxData = null;
		fileContent = null;
		fileOfficeSlides = null;
		currentSlide = 0;
		selectedExcelSheet = '';
		excelWorkbook = null;
	}

	async function blobForPreview() {
		const filename = name;
		const contentType = item?.content_type ?? item?.mime_type ?? '';
		if (localBlob) return { blob: localBlob, filename };
		if (fileId) {
			const data = await getFileContentById(fileId).catch(() => null);
			return data ? { blob: new Blob([data], { type: contentType }), filename } : null;
		}
		if (!terminal) return null;
		return downloadFileBlob(terminal, path);
	}

	async function loadPreview(key: string) {
		const generation = ++previewGeneration;
		const current = () => !destroyed && generation === previewGeneration && key === previewKey;
		loadedKey = key;
		loading = true;
		error = '';
		clearPreview();

		try {
			if (isImage(path) || isVideo(path) || isAudio(path)) {
				const result = await blobForPreview();
				if (!current()) return;
				if (!result) throw new Error(t('Preview failed'));
				const url = URL.createObjectURL(result.blob);
				objectUrls = [...objectUrls, url];
				if (isImage(path)) fileImageUrl = url;
				else if (isVideo(path)) fileVideoUrl = url;
				else fileAudioUrl = url;
			} else if (['glb', 'gltf', 'stl', 'obj', 'ply'].includes(getExt(path)) || isPdf(path) || isSqlite(path)) {
				const result = await blobForPreview();
				if (!current()) return;
				if (!result) throw new Error(t('Preview failed'));
				const buffer = await result.blob.arrayBuffer();
				if (!current()) return;
				if (isPdf(path)) filePdfData = buffer;
				else if (isSqlite(path)) fileSqliteData = buffer;
				else fileModelData = buffer;
			} else if (isOffice(path)) {
				const ext = getExt(path);
				if (ext === 'docx' || ext === 'pptx') {
					const preview = terminal
						? await downloadFilePreview(terminal, path)
						: null;
					if (!current()) return;
					if (preview) {
						const buffer = await preview.blob.arrayBuffer();
						if (current()) filePdfData = buffer;
					} else {
						const result = await blobForPreview();
						if (!current()) return;
						if (!result) throw new Error(t('Preview failed'));
						const buffer = await result.blob.arrayBuffer();
						if (!current()) return;
						if (ext === 'docx') fileDocxData = buffer;
						else {
							const { pptxToImages } = await import('$lib/utils/pptxToHtml');
							if (!current()) return;
							const resultImages = await pptxToImages(buffer);
							if (current()) fileOfficeSlides = resultImages.images;
						}
					}
				} else {
					const result = await blobForPreview();
					if (!current()) return;
					if (!result) throw new Error(t('Preview failed'));
					const arrayBuffer = await result.blob.arrayBuffer();
					const { readExcelWorkbook } = await import('$lib/utils/excelToTable');
					const workbook = await readExcelWorkbook(arrayBuffer);
					if (!current()) return;
					excelWorkbook = workbook;
					selectedExcelSheet = workbook.SheetNames[0] ?? '';
				}
			} else if (fileId || localBlob) {
				const result = await blobForPreview();
				if (!current()) return;
				if (!result) throw new Error(t('Preview failed'));
				if (/^(?:text\/|application\/(?:json|xml|javascript))/.test(result.blob.type) || /\.(?:txt|log|md|markdown|csv|tsv|json|html?|svg|xml|ya?ml|py|js|ts|css|sh|sql|ipynb)$/i.test(path)) {
					const content = await result.blob.text();
					if (current()) fileContent = content;
				}
			} else if (terminal && (!attachment || /^(?:text\/|application\/(?:json|xml|javascript))/.test(item?.content_type ?? item?.mime_type ?? '') || /\.(?:txt|log|md|markdown|csv|tsv|json|html?|svg|xml|ya?ml|py|js|ts|css|sh|sql|ipynb)$/i.test(path))) {
				const content = await readFile(terminal, path);
				if (current()) fileContent = content;
			}
		} catch (e) {
			if (current()) error = e instanceof Error ? e.message : t('Preview failed');
		} finally {
			if (current()) loading = false;
		}
	}

	function openInFiles() {
		if (unavailable || !path) return;
		showTabs.set(true);
		showFileNavPath.set(targetPage ? { path, page: targetPage } : path);
	}

	async function downloadFile() {
		if (unavailable || !path) return;
		const result = await blobForPreview();
		if (!result) {
			toast.error(t('Download failed'));
			return;
		}

		const url = URL.createObjectURL(result.blob);
		const a = document.createElement('a');
		a.href = url;
		a.download = result.filename;
		a.click();
		URL.revokeObjectURL(url);
	}

	onDestroy(() => { destroyed = true; previewGeneration += 1; clearPreview(); });
</script>

<div
	class="my-2 w-full overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-white/8 dark:bg-gray-950/20"
>
	<div
		class="flex h-8 items-center {expanded ? 'border-b border-gray-100 dark:border-white/8' : ''}"
	>
		<button
			type="button"
			class="flex h-full min-w-0 flex-1 items-center gap-2 px-2.5 text-left"
			on:click={() => (expanded = !expanded)}
			aria-expanded={expanded}
			title={name}
		>
			<div
				class="flex size-5 shrink-0 items-center justify-center text-gray-500 dark:text-gray-400"
			>
				<Icon name={fileIconName(name || path || '', 'file')} size={14} />
			</div>
			<div class="min-w-0 flex-1 truncate text-xs font-medium text-gray-800 dark:text-gray-100">
				{name}
			</div>
		</button>

		<button
			type="button"
			class="mr-1 flex size-6 shrink-0 items-center justify-center rounded text-gray-400 transition-colors hover:text-gray-700 disabled:opacity-40 disabled:hover:text-gray-400 dark:text-gray-500 dark:hover:text-gray-200 dark:disabled:hover:text-gray-500"
			disabled={unavailable}
			on:click|stopPropagation={downloadFile}
			aria-label={t('Download')}
			title={t('Download')}
		>
			<Icon name="download" size={13} />
		</button>
		{#if !fileId && !localBlob && selector === $selectedTerminalId}
			<button
				type="button"
				class="mr-1 flex size-6 shrink-0 items-center justify-center rounded text-gray-400 transition-colors hover:text-gray-700 disabled:opacity-40 disabled:hover:text-gray-400 dark:text-gray-500 dark:hover:text-gray-200 dark:disabled:hover:text-gray-500"
				disabled={unavailable}
				on:click|stopPropagation={openInFiles}
				aria-label={t('Open')}
				title={t('Open')}
			>
				<Icon name="external-link" size={13} />
			</button>
		{/if}
	</div>

	{#if expanded}
		{#if unavailable}
			<div class="px-4 py-3 text-xs text-gray-500 dark:text-gray-400">
				{t('Terminal unavailable')}
			</div>
		{:else if error}
			<div class="flex items-center justify-between gap-3 px-4 py-3 text-xs text-red-500 dark:text-red-400">
				<span>{error}</span>
				<button type="button" class="shrink-0 underline" on:click={() => (loadedKey = '')}>{t('Retry')}</button>
			</div>
		{:else}
			<div
				class="{previewClass} max-h-[75vh] min-h-24 resize-y overflow-hidden bg-gray-50 dark:bg-gray-950"
			>
				<FilePreview
					selectedFile={path}
					fileLoading={loading}
					{fileImageUrl}
					{fileVideoUrl}
					{fileAudioUrl}
					{filePdfData}
					{fileSqliteData}
					{fileModelData}
					{fileDocxData}
					{fileContent}
					target={fileId ? null : terminal}
					chatId={effectiveChatId}
					{excelWorkbook}
					{fileOfficeSlides}
					{currentSlide}
					{targetPage}
					bind:selectedExcelSheet
					readOnly={true}
				/>
				{#if !loading && fileImageUrl === null && fileVideoUrl === null && fileAudioUrl === null && filePdfData === null && fileSqliteData === null && fileModelData === null && fileDocxData === null && fileContent === null && excelWorkbook === null && fileOfficeSlides === null}
					<div
						class="flex h-full items-center justify-center px-3 text-xs text-gray-500 dark:text-gray-400"
					>
						{t('No preview available')}
					</div>
				{/if}
			</div>
		{/if}
	{/if}
</div>
