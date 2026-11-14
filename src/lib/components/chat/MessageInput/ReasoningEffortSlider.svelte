<script lang="ts">
	import { createEventDispatcher, getContext } from 'svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Bolt from '$lib/components/icons/Bolt.svelte';
	import ArrowPath from '$lib/components/icons/ArrowPath.svelte';

	const i18n: any = getContext('i18n');
	const dispatch = createEventDispatcher<{ change: string | null }>();
	export let value: string | null = null;
	const levels = ['omit', 'none', null, 'low', 'medium', 'high', 'xhigh', 'max'];
	let editing = false;
	let index = 2;
	$: normalizedValue = value === 'disabled' || value === 'off' ? 'none' : value || null;
	$: selectedIndex = levels.indexOf(normalizedValue);
	$: if (!editing) index = selectedIndex < 0 ? 2 : selectedIndex;
	$: currentValue = editing ? levels[index] : value || null;
	$: label = currentValue === null ? $i18n.t('Default') : currentValue === 'none' || currentValue === 'disabled' || currentValue === 'off' ? 'off' : currentValue;
	$: progress = selectedIndex < 0 && !editing ? 0 : ((index + 0.5) / levels.length) * 100;
	$: hint = $i18n.t('omit skips reasoning parameters; off disables reasoning; Default inherits your settings.');

	const choose = (nextIndex: number) => {
		index = nextIndex;
		editing = false;
		dispatch('change', levels[nextIndex]);
	};
</script>

<div class="space-y-2 px-2 pt-1.5 pb-2.5 text-xs [--reasoning-thumb-size:1.25rem]">
	<div class="flex items-center gap-2">
		<Tooltip content={hint} allowHTML={false}>
			<span class="flex cursor-help items-center gap-1.5 text-gray-500 dark:text-gray-400">
				<Bolt className="size-3.5" />
				<span>{$i18n.t('Reasoning level')}</span>
			</span>
		</Tooltip>
		<span class="min-w-0 flex-1 truncate text-right font-medium text-gray-800 dark:text-gray-100" aria-live="polite">{label}</span>
		<Tooltip content={$i18n.t('Reset reasoning level to default')} allowHTML={false}>
			<button
				type="button"
				aria-label={$i18n.t('Reset reasoning level to default')}
				disabled={currentValue === null}
				class="flex size-5 items-center justify-center rounded-full text-gray-400 transition hover:bg-gray-100 hover:text-gray-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-400 disabled:opacity-30 dark:hover:bg-white/5 dark:hover:text-gray-200"
				on:click={() => choose(2)}
			>
				<ArrowPath className="size-3.5" />
			</button>
		</Tooltip>
	</div>
	<div class="space-y-1">
		<div
			class="relative flex h-6 items-center rounded-full bg-gray-100 [--reasoning-fill:var(--color-gray-300)] dark:bg-white/[0.07] dark:[--reasoning-fill:var(--color-gray-600)]"
			style:background-image={`linear-gradient(to right, var(--reasoning-fill) ${progress}%, transparent ${progress}%)`}
		>
			<div class="pointer-events-none absolute inset-x-[6.25%] h-1" aria-hidden="true">
				{#each levels as level, step}
					<span
						class={`absolute size-1 -translate-x-1/2 rounded-full ${step <= index && (selectedIndex >= 0 || editing) ? 'bg-gray-500/60 dark:bg-gray-300/60' : 'bg-gray-400/40 dark:bg-gray-500/50'}`}
						style:left={`${(step / (levels.length - 1)) * 100}%`}
					></span>
				{/each}
			</div>
			<input
				type="range"
				min="0"
				max={levels.length - 1}
				step="1"
				value={index}
				aria-label={$i18n.t('Reasoning level')}
				aria-valuetext={label}
				class="reasoning-slider absolute h-6 cursor-pointer appearance-none rounded-full bg-transparent outline-offset-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-400"
				on:input={(event) => {
					editing = true;
					index = Number(event.currentTarget.value);
				}}
				on:change={(event) => choose(Number(event.currentTarget.value))}
				on:pointerup={() => {
					if (index === selectedIndex) editing = false;
				}}
				on:blur={() => (editing = false)}
				on:pointercancel={() => (editing = false)}
				on:keydown={(event) => {
					if (['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Home', 'End'].includes(event.key)) event.stopPropagation();
				}}
			/>
		</div>
		<div class="grid grid-cols-8">
			{#each levels as level, step}
				<button
					type="button"
					aria-pressed={editing ? index === step : selectedIndex === step}
					class={`whitespace-nowrap rounded-sm py-1 text-center text-[0.5625rem] leading-3 transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-400 ${((editing && index === step) || (!editing && selectedIndex === step)) ? 'font-medium text-gray-900 dark:text-gray-100' : 'text-gray-400 hover:text-gray-700 dark:text-gray-500 dark:hover:text-gray-300'}`}
					on:click={() => choose(step)}
				>
					{level === null ? $i18n.t('Default') : level === 'none' ? 'off' : level}
				</button>
			{/each}
		</div>
	</div>
</div>

<style>
	.reasoning-slider {
		left: calc(6.25% - var(--reasoning-thumb-size) / 2);
		width: calc(87.5% + var(--reasoning-thumb-size));
		margin: 0;
		padding: 0;
		border: 0;
	}

	.reasoning-slider::-webkit-slider-runnable-track {
		height: 1.5rem;
		border: 0;
		background: transparent;
	}

	.reasoning-slider::-moz-range-track {
		height: 1.5rem;
		border: 0;
		background: transparent;
	}

	.reasoning-slider::-moz-range-progress {
		background: transparent;
	}

	.reasoning-slider::-webkit-slider-thumb {
		appearance: none;
		box-sizing: border-box;
		width: var(--reasoning-thumb-size);
		height: var(--reasoning-thumb-size);
		margin-top: calc((1.5rem - var(--reasoning-thumb-size)) / 2);
		border: 1px solid #0000000d;
		border-radius: 50%;
		background: white;
		box-shadow: 0 1px 3px #0003;
	}

	.reasoning-slider::-moz-range-thumb {
		box-sizing: border-box;
		width: var(--reasoning-thumb-size);
		height: var(--reasoning-thumb-size);
		border: 1px solid #0000000d;
		border-radius: 50%;
		background: white;
		box-shadow: 0 1px 3px #0003;
	}
</style>
