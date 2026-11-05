import type { i18n } from 'i18next';
import { canSearchSetting } from './settings-access';

export type SettingsTab = {
	id: string;
	titleKey: string;
	title?: string;
	searchPrefixes: string[];
};
export type SettingsAccessContext = { user: any; config: any };
export type SettingsSearchEntry = {
	key: string | null;
	label: string;
	labels: string[];
	contentTexts: string[];
	texts: string[];
};
export type SettingsSearchIndex = { id: string; entries: SettingsSearchEntry[] }[];
export type SettingsSearchResult = { tabId: string; entry: SettingsSearchEntry };

export const normalizeSettingsSearch = (text: string): string =>
	text
		.toLowerCase()
		.normalize('NFD')
		.replace(/(\p{Script=Latin})\p{M}+/gu, '$1')
		.normalize('NFC')
		.replace(/[^\p{L}\p{M}\p{N}]+/gu, ' ')
		.trim()
		.replace(/\s+/g, ' ');

export function buildSettingsSearchIndex(
	tabs: SettingsTab[],
	english: Record<string, string>,
	translator: Pick<i18n, 't'>,
	context: SettingsAccessContext
): SettingsSearchIndex {
	const variants = (key: string) => {
		const fallback = english[key] || (key.startsWith('settings.') ? '' : key);
		return [
			...new Set(
				[
					translator.t(key, { lng: 'en-US', defaultValue: fallback }),
					translator.t(key, { defaultValue: fallback })
				].filter(
					(text): text is string =>
						typeof text === 'string' &&
						!!text.trim() &&
						(!key.startsWith('settings.') || text !== key)
				)
			)
		]
			.map(normalizeSettingsSearch)
			.filter(Boolean);
	};
	const displayText = (key: string) => {
		const fallback = english[key] || key;
		const translated = translator.t(key, { defaultValue: fallback });
		return typeof translated === 'string' && translated.trim() ? translated : fallback;
	};
	const keys = Object.keys(english).filter((key) => /\.(label|title)$/.test(key));
	return tabs.map((tab) => {
		const location = [
			...variants(tab.titleKey),
			...variants(tab.id.startsWith('admin:') ? 'Admin' : 'Personal')
		];
		const entries = keys
			.filter(
				(key) =>
					tab.searchPrefixes.some((prefix) => key.startsWith(prefix)) &&
					canSearchSetting(key, tab.id, context)
			)
			.map((key) => {
				const labels = variants(key);
				const contentTexts = [
					...labels,
					...variants(key.replace(/\.(label|title)$/, '.description'))
				];
				return {
					key,
					label: displayText(key),
					labels,
					contentTexts,
					texts: [...contentTexts, ...location]
				};
			});
		// The tab itself is always a destination, including panels with only dynamic records.
		return {
			id: tab.id,
			entries: [
				{
					key: null,
					label: displayText(tab.titleKey),
					labels: location,
					contentTexts: location,
					texts: location
				},
				...entries
			]
		};
	});
}

const entryMatches = (entry: SettingsSearchEntry, words: string[], contentOnly = false) =>
	words.every((word) =>
		(contentOnly ? entry.contentTexts : entry.texts).some((text) => text.includes(word))
	);

const entryScore = (entry: SettingsSearchEntry, query: string, words: string[]) => {
	if (entry.labels.some((label) => label === query)) return 0;
	if (entry.labels.some((label) => label.startsWith(query))) return 1;
	if (words.every((word) => entry.labels.some((label) => label.includes(word)))) return 2;
	return 3;
};

export function searchSettingsTabs(index: SettingsSearchIndex, query: string): string[] {
	const words = normalizeSettingsSearch(query).split(' ').filter(Boolean);
	return index
		.filter(
			(tab) => !words.length || tab.entries.some((entry) => entryMatches(entry, words))
		)
		.map((tab) => tab.id);
}

export function searchSettingsEntries(
	index: SettingsSearchIndex,
	query: string
): SettingsSearchResult[] {
	const normalizedQuery = normalizeSettingsSearch(query);
	const words = normalizedQuery.split(' ').filter(Boolean);
	if (!words.length) return [];

	return index
		.flatMap((tab) =>
			tab.entries
				.filter((entry) => entry.key && entryMatches(entry, words, true))
				.map((entry) => ({
					tabId: tab.id,
					entry,
					score: entryScore(entry, normalizedQuery, words)
				}))
		)
		.sort((a, b) => a.score - b.score)
		.map(({ tabId, entry }) => ({ tabId, entry }));
}

export function getSettingsSearchMatch(
	index: SettingsSearchIndex,
	tabId: string,
	query: string
): SettingsSearchEntry | null {
	const normalizedQuery = normalizeSettingsSearch(query);
	const words = normalizedQuery.split(' ').filter(Boolean);
	if (!words.length) return null;

	const candidates =
		index
			.find((tab) => tab.id === tabId)
			?.entries.filter((entry) => entryMatches(entry, words, Boolean(entry.key))) ?? [];

	return (
		candidates
			.map((entry, order) => ({
				entry,
				order,
				score: entry.key ? entryScore(entry, normalizedQuery, words) : 4
			}))
			.sort((a, b) => a.score - b.score || a.order - b.order)[0]?.entry ?? null
	);
}
