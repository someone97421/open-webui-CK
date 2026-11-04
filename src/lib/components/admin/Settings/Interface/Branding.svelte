<script lang="ts">
	import { getContext, onDestroy } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { WEBUI_BASE_URL } from '$lib/constants';
	import { uploadInterfaceLogo, type InterfaceBranding } from '$lib/apis/configs';
	import Photo from '$lib/components/icons/Photo.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import AdminSettingSection from '../AdminSettingSection.svelte';
	import AdminSettingField from '../AdminSettingField.svelte';

	export let value: InterfaceBranding = { name: '', logo_url: '' };
	export let disabled = false;
	export let uploading = false;
	const i18n: any = getContext('i18n');
	const inputClass = 'h-8 w-full rounded-lg border border-gray-100/50 bg-gray-50/40 px-2 text-xs text-gray-700 outline-hidden placeholder:text-gray-400 focus:border-blue-400 disabled:opacity-50 dark:border-white/[0.04] dark:bg-white/[0.03] dark:text-gray-300';
	const buttonClass = 'h-8 shrink-0 rounded-lg border border-gray-200 px-2.5 text-xs text-gray-600 hover:bg-gray-50 disabled:opacity-50 dark:border-white/10 dark:text-gray-300 dark:hover:bg-white/5';
	let fileInput: HTMLInputElement;
	let previewUrl = '';
	let previewTarget: string | null = null;
	let previewFailed = false;
	let previewTimer: ReturnType<typeof setTimeout>;
	let uploadController: AbortController | null = null;
	let disposed = false;

	function schedulePreview(url: string) {
		if (url === previewTarget) return;
		previewTarget = url;
		clearTimeout(previewTimer);
		previewTimer = setTimeout(() => {
			previewFailed = false;
			const target = url.trim();
			if (target.startsWith('/api/v1/configs/interface/branding/logo/')) {
				previewUrl = `${WEBUI_BASE_URL}${target}`;
			} else {
				try {
					const parsed = new URL(target);
					previewUrl = ['http:', 'https:'].includes(parsed.protocol) ? parsed.href : '';
				} catch {
					previewUrl = '';
				}
			}
		}, 250);
	}

	$: schedulePreview(value.logo_url);

	async function selectImage(event: Event) {
		const input = event.currentTarget as HTMLInputElement;
		const file = input.files?.[0];
		if (!file || uploading || disabled) return;
		if (file.size > 10 * 1024 * 1024) {
			toast.error($i18n.t('settings.admin.interface.branding.imageSizeError'));
			input.value = '';
			return;
		}
		uploading = true;
		uploadController = new AbortController();
		try {
			const result = await uploadInterfaceLogo(localStorage.token, file, uploadController.signal);
			if (!disposed) value = { ...value, logo_url: result.url };
		} catch (error) {
			if (!disposed) toast.error(Array.isArray(error) ? error.map((entry) => entry.msg).join('\n') : String(error));
		} finally {
			input.value = '';
			if (!disposed) uploading = false;
			uploadController = null;
		}
	}

	onDestroy(() => {
		disposed = true;
		clearTimeout(previewTimer);
		uploadController?.abort();
	});
</script>

<AdminSettingSection first title={$i18n.t('settings.admin.interface.branding.title')}>
	<fieldset disabled={disabled || uploading} class="flex min-w-0 flex-col gap-3">
		<AdminSettingField label={$i18n.t('settings.admin.interface.branding.name')} forId="website-name">
			<input id="website-name" class={inputClass} type="text" maxlength="128" bind:value={value.name} placeholder="Open WebUI" title={$i18n.t('settings.admin.interface.branding.nameHint')} />
		</AdminSettingField>
		<AdminSettingField label={$i18n.t('settings.admin.interface.branding.logo')} forId="website-logo-url">
			<div class="flex min-w-0 items-center gap-3">
				<div class="flex size-14 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-gray-100 bg-gray-50 dark:border-white/10 dark:bg-white/5" title={$i18n.t(previewFailed ? 'settings.admin.interface.branding.previewError' : 'settings.admin.interface.branding.logoHint')}>
					{#if uploading}
						<Spinner className="size-5" />
					{:else if previewUrl && !previewFailed}
						{#key previewUrl}<img src={previewUrl} alt={$i18n.t('settings.admin.interface.branding.logo')} class="size-full object-contain" on:error={() => (previewFailed = true)} />{/key}
					{:else}
						<Photo className="size-6 text-gray-400" />
					{/if}
				</div>
				<div class="flex min-w-0 flex-1 flex-col gap-2">
					<input id="website-logo-url" class={inputClass} type="text" inputmode="url" maxlength="2048" bind:value={value.logo_url} placeholder="https://example.com/logo.png" title={$i18n.t('settings.admin.interface.branding.logoHint')} />
					<div class="flex flex-wrap gap-2">
						<input bind:this={fileInput} class="hidden" type="file" accept="image/png,image/jpeg,image/webp,image/gif,image/x-icon,image/vnd.microsoft.icon,.ico" on:change={selectImage} aria-label={$i18n.t('settings.admin.interface.branding.chooseImage')} />
						<button type="button" class={buttonClass} on:click={() => fileInput?.click()} title={$i18n.t('settings.admin.interface.branding.uploadHint')}>{$i18n.t(uploading ? 'Uploading...' : 'settings.admin.interface.branding.chooseImage')}</button>
						<button type="button" class={buttonClass} disabled={!value.logo_url} on:click={() => (value = { ...value, logo_url: '' })} title={$i18n.t('settings.admin.interface.branding.resetHint')}>{$i18n.t('Reset')}</button>
					</div>
				</div>
			</div>
		</AdminSettingField>
	</fieldset>
</AdminSettingSection>
