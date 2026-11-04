import { get } from 'svelte/store';
import { v4 as uuidv4 } from 'uuid';

import { chatId, config, pyodideWorker, user } from '$lib/stores';
import { isTemporaryChatId } from '$lib/utils/chatId';
import { PyodideSandboxHost } from '$lib/pyodide/pyodideSandboxHost';
import PyodideWorker from '$lib/workers/pyodide.worker?worker';

export type PyodideScope = {
	userId: string;
	chatId: string;
	key: string;
	persistent: boolean;
	generation: number;
};

let draftId: string | null = null;
let visibleScope: string | null = null;
let previousChatId: string | null = null;
let sessionGeneration = 0;
let runtime: { worker: Worker; key: string; persistent: boolean } | null = null;
let running: Job | null = null;
const queue: Job[] = [];

type Job = {
	owner: ScopedPyodideWorker;
	scope: PyodideScope;
	message: Record<string, any>;
	transfer: Transferable[];
	cancel?: () => void;
};

export function getPyodideScope(targetChatId?: string | null): PyodideScope {
	const userId = get(user)?.id ?? '';
	const visibleChatId = get(chatId);
	if (!visibleChatId && previousChatId) draftId = null;
	previousChatId = visibleChatId;
	const currentChatId = targetChatId || visibleChatId;
	if (!draftId) draftId = `draft-${uuidv4()}`;
	const scopedChatId = currentChatId || draftId;
	return {
		userId,
		chatId: scopedChatId,
		key: `${encodeURIComponent(userId).replace(/\./g, '%2E')}/${encodeURIComponent(scopedChatId).replace(/\./g, '%2E')}`,
		persistent: !!userId && !!currentChatId && !isTemporaryChatId(currentChatId),
		generation: sessionGeneration
	};
}

const isCurrentScope = (scope: PyodideScope) =>
	!!scope.userId && get(user)?.id === scope.userId && getPyodideScope().key === scope.key;

function stopRuntime(instance = runtime) {
	if (!instance) return;
	instance.worker.terminate();
	if (runtime === instance) runtime = null;
}

/** 切换界面只发布对应 scope 的代理；正在运行的旧会话请求保留自己的回调。 */
export function activatePyodideScope() {
	const scope = getPyodideScope();
	if (visibleScope === scope.key) return;
	visibleScope = scope.key;
	if (!running && runtime?.key !== scope.key) stopRuntime();
	pyodideWorker.set(scope.userId ? createPyodideWorker(scope) : null);
	if (typeof window !== 'undefined') {
		window.dispatchEvent(new CustomEvent('pyodide:scope', { detail: scope.key }));
	}
}

export function clearPyodideRuntime() {
	sessionGeneration++;
	previousChatId = null;
	visibleScope = null;
	draftId = null;
	for (const job of queue.splice(0)) job.owner.fail(job.message, 'Python session closed');
	running?.cancel?.();
	stopRuntime();
	pyodideWorker.set(null);
}

async function drainQueue() {
	if (running) return;
	const job = queue.shift();
	if (!job) return;
	running = job;
	const { owner, scope, message, transfer } = job;
	try {
		if (!owner.available(scope)) throw new Error('Python context changed');
		const persistent = scope.persistent && !!get(config)?.features?.enable_pyodide_file_persistence;
		if (runtime && (runtime.key !== scope.key || runtime.persistent !== persistent)) stopRuntime();
		if (!runtime) {
			runtime = {
				key: scope.key,
				persistent,
				worker: persistent ? new PyodideWorker() : (new PyodideSandboxHost() as unknown as Worker)
			};
		}
		const instance = runtime;
		const response = await new Promise<Record<string, any>>((resolve, reject) => {
			const cleanup = () => {
				clearTimeout(timeout);
				instance.worker.removeEventListener('message', onMessage);
				instance.worker.removeEventListener('error', onError);
			};
			const onMessage = (event: MessageEvent) => {
				if (event.data?.id !== message.id) return;
				cleanup();
				resolve(event.data);
			};
			const onError = (event: ErrorEvent) => {
				cleanup();
				stopRuntime(instance);
				reject(new Error(event.message || 'Python runtime error'));
			};
			job.cancel = () => {
				cleanup();
				stopRuntime(instance);
				reject(new Error('Python session closed'));
			};
			const timeout = setTimeout(() => {
				cleanup();
				stopRuntime(instance);
				reject(new Error('Execution Time Limit Exceeded'));
			}, 60000);
			instance.worker.addEventListener('message', onMessage);
			instance.worker.addEventListener('error', onError);
			try {
				instance.worker.postMessage({ ...message, scope: scope.key }, transfer);
			} catch (error) {
				cleanup();
				stopRuntime(instance);
				reject(error);
			}
		});
		job.cancel = undefined;
		if (owner.available(scope)) owner.deliver(response);
		else owner.fail(message, 'Python context changed');
	} catch (error) {
		owner.fail(message, error instanceof Error ? error.message : String(error));
	} finally {
		job.cancel = undefined;
		running = null;
		void drainQueue();
	}
}

class ScopedPyodideWorker {
	onmessage: ((event: MessageEvent) => void) | null = null;
	onerror: ((event: ErrorEvent) => void) | null = null;
	private listeners = new Set<(event: MessageEvent) => void>();
	private errorListeners = new Set<(event: ErrorEvent) => void>();
	private terminated = false;
	private generation = sessionGeneration;

	constructor(private readonly scope: PyodideScope | undefined, private readonly background: boolean) {}

	available(scope: PyodideScope) {
		return !this.terminated && this.generation === sessionGeneration && scope.generation === sessionGeneration &&
			!!scope.userId && get(user)?.id === scope.userId && (this.background || isCurrentScope(scope));
	}

	postMessage(message: Record<string, any>, transfer: Transferable[] = []) {
		queue.push({ owner: this, scope: this.scope ?? getPyodideScope(), message: { ...message }, transfer });
		// 兼容先 postMessage 再注册监听器的旧调用点。
		queueMicrotask(() => void drainQueue());
	}

	addEventListener(type: string, listener: any) {
		if (type === 'message') this.listeners.add(listener);
		else if (type === 'error') this.errorListeners.add(listener);
	}

	removeEventListener(type: string, listener: any) {
		if (type === 'message') this.listeners.delete(listener);
		else if (type === 'error') this.errorListeners.delete(listener);
	}

	deliver(data: Record<string, any>) {
		const event = new MessageEvent('message', { data });
		this.onmessage?.(event);
		for (const listener of [...this.listeners]) listener(event);
	}

	fail(message: Record<string, any>, error: string) {
		this.deliver({
			id: message.id,
			type: message.type,
			error,
			stderr: error,
			stdout: null,
			result: null,
			success: false
		});
	}

	terminate() {
		this.terminated = true;
		for (let i = queue.length - 1; i >= 0; i--) {
			if (queue[i].owner === this) {
				const [job] = queue.splice(i, 1);
				this.fail(job.message, 'Python session closed');
			}
		}
		if (running?.owner === this) running.cancel?.();
		this.listeners.clear();
		this.errorListeners.clear();
		this.onmessage = null;
		this.onerror = null;
	}
}

export const createPyodideWorker = (
	scope?: PyodideScope,
	{ background = false } = {}
): Worker => new ScopedPyodideWorker(scope, background) as unknown as Worker;
