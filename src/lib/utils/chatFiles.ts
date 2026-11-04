export type ChatFileReference =
	| { kind: 'stored'; fileId: string }
	| { kind: 'workspace'; path: string; terminalId?: string; chatId?: string };

export function parseChatFileLink(href: string, origin: string): ChatFileReference | null {
	const value = href.trim();
	if (!value) return null;
	if (/^(?:sandbox:|file:)/i.test(value)) {
		try {
			const path = new URL(value).pathname;
			return { kind: 'workspace', path: decodeURIComponent(path) };
		} catch {
			return null;
		}
	}
	try {
		const url = new URL(value, origin);
		if (url.origin !== origin) return null;
		const stored = url.pathname.match(/\/api\/v1\/files\/([^/]+)\/content(?:\/[^/]+)?$/);
		if (stored) return { kind: 'stored', fileId: decodeURIComponent(stored[1]) };
		const terminal = url.pathname.match(/\/api\/v1\/terminals\/([^/]+)(?:\/chats\/([^/]+))?\/files\/(view|read|serve(?:\/.*)?)$/);
		if (terminal) {
			const path = terminal[3].startsWith('serve/')
				? decodeURIComponent(terminal[3].slice('serve'.length))
				: url.searchParams.get('path');
			if (path) return {
				kind: 'workspace', path,
				terminalId: decodeURIComponent(terminal[1]),
				chatId: terminal[2] ? decodeURIComponent(terminal[2]) : undefined
			};
		}
	} catch {
		return null;
	}
	if (/^(?:[a-z][a-z\d+.-]*:|\/\/)/i.test(value)) return null;
	const localPath = value.split(/[?#]/)[0];
	if (/^\/(?:mnt|workspaces?|home|tmp|root)\//.test(localPath) || /^\.{1,2}\//.test(localPath) || /^(?!\/)[^?#]+\.[a-z\d]{1,12}$/i.test(localPath)) {
		let path = localPath;
		try { path = decodeURIComponent(localPath); } catch { path = localPath; }
		return { kind: 'workspace', path };
	}
	return null;
}

export function fileContentType(path: string): string {
	const types: Record<string, string> = {
		pdf: 'application/pdf', png: 'image/png', jpg: 'image/jpeg', jpeg: 'image/jpeg',
		gif: 'image/gif', webp: 'image/webp', svg: 'image/svg+xml',
		txt: 'text/plain', md: 'text/markdown', html: 'text/html', htm: 'text/html',
		csv: 'text/csv', json: 'application/json', zip: 'application/zip',
		mp4: 'video/mp4', webm: 'video/webm', mp3: 'audio/mpeg', wav: 'audio/wav',
		docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
		xlsx: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
		pptx: 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
	};
	return types[path.split('.').pop()?.toLowerCase() ?? ''] ?? 'application/octet-stream';
}

export function isChatFileAttachment(value: any): boolean {
	return value?.type === 'file' && typeof value.path === 'string' && !!value.path &&
		value.exists !== false && !value.error &&
		(value.source === 'open_webui' || (value.source === 'open_terminal' && !!value.terminal_selector));
}

export function chatFileAttachmentKey(item: any): string {
	return JSON.stringify([
		item.source, item.terminal_selector ?? '', item.session_id ?? '',
		item.full_path || item.path, item.page ?? null
	]);
}
