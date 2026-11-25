import { get, writable } from 'svelte/store';
import { toast } from 'svelte-sonner';
import { WEBUI_API_BASE_URL } from '$lib/constants';
import { v4 as uuidv4 } from 'uuid';

const extensionOrigin = /^chrome-extension:\/\/[a-p]{32}$/;
const identifier = /^[a-zA-Z0-9_-]{16,128}$/;

type BrowserBinding = {
	bindingId: string; socketToken: string; pairCode: string; userId: string; relayPort: number;
	replacesBindingId?: string;
};
type BrowserTab = { tabId: number; title: string; url: string; kind: 'page' };
type BrowserContext = { tabId?: number; relayTabId?: number; title?: string; url?: string };
export type BrowserReference = {
	kind: 'page' | 'selection' | 'element';
	tabId: number;
	title: string;
	url: string;
	preview: string;
	text: string;
};
type Composer = { key: string; focus: () => void; insert: (reference: BrowserReference) => boolean };

type SidebarState = {
	active: boolean;
	bindingId: string;
	busy: boolean;
	borrowed: boolean;
	handoff: boolean;
	context: BrowserContext | null;
	tabs: BrowserTab[];
	error: string;
};
const emptyState: SidebarState = {
	active: false, bindingId: '', busy: false, borrowed: false, handoff: false, context: null, tabs: [], error: ''
};
export const browserSidebar = writable<SidebarState>(emptyState);
let parentOrigin = '';
let deviceId = '';
let userId = '';
let binding: BrowserBinding | undefined;
let controller: AbortController | undefined;
let bindingAuthToken = '';
let pendingBindingRefresh: string | undefined;
let composer: Composer | undefined;
let initialDraftKey = '';
let pickerResultSession: string | undefined;
const pending = new Map<string, (result: string) => void>();

function post(type: string, fields: Record<string, unknown> = {}) {
	if (parentOrigin) window.parent.postMessage({ type: `openwebui:${type}`, ...fields }, parentOrigin);
}

function status() {
	post('remote-status', {
		authenticated: !!userId,
		online: true,
		canCompose: !!composer,
		userId,
		draftKey: composer?.key,
		initialDraftKey
	});
}

function clearBinding() {
	controller?.abort();
	controller = undefined;
	binding = undefined;
	bindingAuthToken = '';
	pendingBindingRefresh = undefined;
	pickerResultSession = undefined;
	browserSidebar.set({ ...emptyState, active: !!parentOrigin });
}

async function bind({ renew = false, expectedBindingId }: { renew?: boolean; expectedBindingId?: string } = {}) {
	if (!userId || !deviceId || (binding && !renew && !expectedBindingId)) return;
	if (controller) {
		if (expectedBindingId) pendingBindingRefresh = expectedBindingId;
		return;
	}
	const authToken = localStorage.getItem('token');
	if (!authToken) return;
	const expectedUser = userId;
	const previous = renew ? binding : undefined;
	const request = new AbortController();
	controller = request;
	try {
		if (previous) {
			const retired = await fetch(`${WEBUI_API_BASE_URL}/browser/bind/${encodeURIComponent(previous.bindingId)}`, {
				method: 'DELETE', signal: request.signal, headers: { Authorization: `Bearer ${previous.socketToken}` }
			});
			if (!retired.ok) throw new Error('浏览器连接不可用，请检查 NAS 的扩展配置。');
		}
		const response = await fetch(`${WEBUI_API_BASE_URL}/browser/bind`, {
			method: 'POST', signal: request.signal,
			headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${authToken}` },
			body: JSON.stringify({ deviceId, extensionOrigin: parentOrigin })
		});
		if (!response.ok) {
			const detail = (await response.json().catch(() => null))?.detail;
			if (response.status === 401 || detail === 'browse_session_invalid') throw new Error('请重新登录 Open WebUI，再连接浏览器。');
			if (detail === 'browse_origin_denied') throw new Error('NAS 未授权此扩展，请核对扩展 ID。');
			if (detail === 'browse_auth_unavailable') throw new Error('暂时无法验证登录状态，请稍后重试。');
			if (response.status === 429) throw new Error('当前账号的浏览器连接名额已满，请释放连接后重试。');
			throw new Error('浏览器连接不可用，请检查 NAS 的扩展配置。');
		}
		const result: BrowserBinding = await response.json();
		if (result.userId !== expectedUser || !identifier.test(result.bindingId) ||
			!identifier.test(result.socketToken) || typeof result.pairCode !== 'string' ||
			!Number.isInteger(result.relayPort) || result.relayPort < 1 || result.relayPort > 65535) {
			throw new Error('浏览器连接凭据无效。');
		}
		if (request.signal.aborted || userId !== expectedUser || localStorage.getItem('token') !== authToken) return;
		if (expectedBindingId && result.bindingId !== expectedBindingId) return;
		if (binding && binding.bindingId !== result.bindingId) {
			browserSidebar.set({ ...emptyState, active: true });
		}
		binding = { ...result, ...(previous && previous.bindingId !== result.bindingId ? { replacesBindingId: previous.bindingId } : {}) };
		bindingAuthToken = authToken;
		browserSidebar.update((value) => ({ ...value, error: '' }));
		post('browser-binding', binding);
	} catch (error) {
		if (request.signal.aborted || expectedBindingId) return;
		const message = error instanceof Error ? error.message : '浏览器连接失败。';
		browserSidebar.update((value) => ({ ...value, error: message }));
		post('browser-binding', { userId: expectedUser, error: message });
	} finally {
		if (controller === request) {
			controller = undefined;
			const refresh = pendingBindingRefresh;
			pendingBindingRefresh = undefined;
			if (refresh && refresh !== binding?.bindingId) void bind({ expectedBindingId: refresh });
		}
	}
}

function parseReference(value: unknown): BrowserReference | undefined {
	if (!value || typeof value !== 'object') return;
	const ref = value as Record<string, unknown>;
	const { tabId, kind } = ref;
	if (typeof tabId !== 'number' || !Number.isSafeInteger(tabId) || typeof ref.url !== 'string') return;
	try {
		if (!['https:', 'http:'].includes(new URL(ref.url).protocol)) return;
	} catch { return; }
	const title = typeof ref.title === 'string' ? ref.title.slice(0, 256) : '';
	const url = ref.url.slice(0, 2048);
	const page = `${title ? `${title} ` : ''}${url}`;
	const base = { tabId, title, url };
	if (kind === 'page') return { ...base, kind, preview: url, text: `网页引用：${page}` };
	if (kind === 'selection' && typeof ref.selection === 'string') {
		const selection = ref.selection.slice(0, 12000);
		return { ...base, kind, preview: `${url}\n\n${selection}`, text: `网页选文：${page}\n${selection}` };
	}
	if (kind === 'element' && ref.element && typeof ref.element === 'object') {
		const element = ref.element as Record<string, unknown>;
		const details = [element.locator, element.text, element.html]
			.filter((value): value is string => typeof value === 'string')
			.map((value) => value.slice(0, 4000)).join('\n');
		return { ...base, kind, preview: `${url}\n\n${details}`, text: `网页元素：${page}\n${details}` };
	}
}

export function insertBrowserTab(tab: BrowserTab) {
	const reference = parseReference(tab);
	if (reference) composer?.insert(reference);
}

export function requestBrowserAction(method: 'toggleAttach' | 'insertCurrent' | 'handoff'): Promise<string> {
	if (!parentOrigin) return Promise.resolve('浏览器侧栏未连接。');
	const requestId = uuidv4();
	return new Promise((resolve) => {
		const timer = setTimeout(() => {
			pending.delete(requestId);
			resolve('浏览器未响应。');
		}, 15_000);
		pending.set(requestId, (error) => { clearTimeout(timer); resolve(error); });
		post('browse-request', { requestId, method });
	});
}

export function sendElementPicker(action: 'start' | 'end', sessionId: string) {
	if (!parentOrigin) return;
	if (action === 'start') pickerResultSession = sessionId;
	post('element-picker', { action, sessionId });
}

function receive(event: MessageEvent) {
	if (event.source !== window.parent || event.origin !== parentOrigin || !event.data) return;
	const data = event.data;
	if (data.type === 'openwebui:status-request' && typeof data.deviceId === 'string' && identifier.test(data.deviceId)) {
		if (deviceId && deviceId !== data.deviceId) return;
		deviceId = data.deviceId;
		if (binding && localStorage.getItem('token') !== bindingAuthToken) clearBinding();
		status();
		const expectedBindingId = typeof data.expectedBindingId === 'string' && identifier.test(data.expectedBindingId)
			? data.expectedBindingId : undefined;
		if (data.renew === true && data.renewBindingId === binding?.bindingId) void bind({ renew: true });
		else if (expectedBindingId && binding?.bindingId !== expectedBindingId) void bind({ expectedBindingId });
		else if (binding) post('browser-binding', binding);
		else void bind();
	} else if (data.type === 'openwebui:browse-status' && userId) {
		const connected = !!binding && data.bindingId === binding.bindingId;
		browserSidebar.update((value) => ({
			...value, bindingId: connected ? binding!.bindingId : '', busy: data.busy === true,
			borrowed: connected && data.borrowed === true, handoff: connected && data.handoff === true,
			context: connected ? data.browserContext ?? null : null,
			tabs: connected ? value.tabs : [],
			error: typeof data.error === 'string' ? data.error : connected ? '' : value.error
		}));
	} else if (data.type === 'openwebui:browser-tabs' && binding && data.bindingId === binding.bindingId) {
		const tabs = data.active && Array.isArray(data.tabs)
			? data.tabs.slice(0, 150).filter((tab: BrowserTab) => tab?.kind === 'page' && parseReference(tab))
			: [];
		browserSidebar.update((value) => ({ ...value, tabs }));
	} else if (data.type === 'openwebui:request' && typeof data.requestId === 'string') {
		const target = composer;
		const valid = !!target && !!userId && !!binding && data.bindingId === binding.bindingId &&
			get(browserSidebar).bindingId === binding.bindingId && (!data.draftKey || data.draftKey === target.key);
		let ok = false;
		if (valid && data.method === 'browser.insertReference') {
			const reference = parseReference(data.reference);
			if (reference) ok = target.insert(reference);
		} else if (valid && data.method === 'browser.focusComposer') {
			target.focus();
			ok = true;
		}
		post('response', {
			requestId: data.requestId, ok,
			...(ok ? { result: { inserted: true, clientId: data.requestId, draftKey: target?.key } } : { error: '当前对话输入框不可用。' })
		});
	} else if (data.type === 'openwebui:element-picker-result') {
		if (!pickerResultSession || data.sessionId !== pickerResultSession || typeof data.ok !== 'boolean') return;
		pickerResultSession = undefined;
		if (!data.ok) {
			toast.error(typeof data.error === 'string' && data.error ? data.error : '网页元素引用失败，请重试。');
		}
	} else if (data.type === 'openwebui:browse-response') {
		const done = pending.get(data.requestId);
		pending.delete(data.requestId);
		done?.(data.ok ? '' : String(data.error ?? '浏览器操作失败。'));
	}
}

export function mountBrowserSidebar() {
	if (window.parent === window) return;
	const query = new URLSearchParams(location.search);
	const origin = (query.get('browse') === '1' ? query.get('parentOrigin') : null)
		?? sessionStorage.getItem('openwebui:browse-parent');
	if (!origin || !extensionOrigin.test(origin)) return;
	parentOrigin = origin;
	sessionStorage.setItem('openwebui:browse-parent', origin);
	browserSidebar.set({ ...emptyState, active: true });
	window.addEventListener('message', receive);
	status();
	return () => {
		window.removeEventListener('message', receive);
		parentOrigin = '';
		clearBinding();
		deviceId = '';
		userId = '';
		composer = undefined;
		initialDraftKey = '';
	};
}

export function setBrowserSidebarUser(id: string) {
	if (userId === id && (!binding || localStorage.getItem('token') === bindingAuthToken)) return;
	clearBinding();
	userId = id;
	initialDraftKey = composer?.key ?? '';
	status();
	void bind();
}

export function registerBrowserComposer(target: Composer) {
	composer = target;
	if (!initialDraftKey) initialDraftKey = target.key;
	status();
	return () => {
		if (composer !== target) return;
		composer = undefined;
		status();
	};
}

export function browserRequestContext() {
	const state = get(browserSidebar);
	const tab = state.borrowed ? state.context?.relayTabId ?? state.context?.tabId : undefined;
	return state.bindingId ? {
		browser_binding_id: state.bindingId,
		...(Number.isSafeInteger(tab) ? { browser_tab_id: tab } : {})
	} : {};
}
