<script lang="ts">
	import { WEBUI_BASE_URL } from '$lib/constants';
	import { WEBUI_LOGO } from '$lib/stores';

	export let id: string | undefined = undefined;
	export let alt = '';
	export let className = 'size-6';
	const fallback = `${WEBUI_BASE_URL}/favicon.png`;
	let failedSource = '';
	$: source = failedSource === $WEBUI_LOGO ? fallback : $WEBUI_LOGO;
</script>

<img
	{id}
	src={source}
	{alt}
	class="object-contain {className}"
	on:error={() => { if (source !== fallback) failedSource = $WEBUI_LOGO; }}
/>
