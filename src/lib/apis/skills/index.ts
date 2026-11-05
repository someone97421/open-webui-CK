import { WEBUI_API_BASE_URL } from '$lib/constants';

export const createNewSkill = async (token: string, skill: object) => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/skills/create`, {
		method: 'POST',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		},
		body: JSON.stringify({
			...skill
		})
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const getSkills = async (token: string = '', query: string | null = null) => {
	let error = null;

	const searchParams = new URLSearchParams();
	if (query) searchParams.append('query', query);

	const res = await fetch(`${WEBUI_API_BASE_URL}/skills/?${searchParams.toString()}`, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.then((json) => {
			return json;
		})
		.catch((err) => {
			error = err.detail;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const getSkillList = async (token: string = '') => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/skills/list`, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.then((json) => {
			return json;
		})
		.catch((err) => {
			error = err.detail;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const getSkillItems = async (
	token: string = '',
	query: string | null = null,
	viewOption: string | null = null,
	page: number | null = null,
	orderBy: string | null = null,
	direction: string | null = null,
	signal?: AbortSignal
) => {
	let error = null;

	const searchParams = new URLSearchParams();
	if (query) searchParams.append('query', query);
	if (viewOption) searchParams.append('view_option', viewOption);
	if (page) searchParams.append('page', page.toString());
	if (orderBy) searchParams.append('order_by', orderBy);
	if (direction) searchParams.append('direction', direction);

	const res = await fetch(`${WEBUI_API_BASE_URL}/skills/list?${searchParams.toString()}`, {
		method: 'GET',
		signal,
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.then((json) => {
			return json;
		})
		.catch((err) => {
			if (signal?.aborted) return null;
			error = err;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const exportSkills = async (token: string = '') => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/skills/export`, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.then((json) => {
			return json;
		})
		.catch((err) => {
			error = err.detail;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const getSkillById = async (token: string, id: string) => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/skills/id/${id}`, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.then((json) => {
			return json;
		})
		.catch((err) => {
			error = err.detail;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const updateSkillById = async (token: string, id: string, skill: object) => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/skills/id/${id}/update`, {
		method: 'POST',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		},
		body: JSON.stringify({
			...skill,
			access_grants: undefined
		})
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const updateSkillAccessGrants = async (token: string, id: string, accessGrants: any[]) => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/skills/id/${id}/access/update`, {
		method: 'POST',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		},
		body: JSON.stringify({
			access_grants: accessGrants
		})
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const toggleSkillById = async (token: string, id: string) => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/skills/id/${id}/toggle`, {
		method: 'POST',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.then((json) => {
			return json;
		})
		.catch((err) => {
			error = err.detail;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const deleteSkillById = async (token: string, id: string) => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/skills/id/${id}/delete`, {
		method: 'DELETE',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.then((json) => {
			return json;
		})
		.catch((err) => {
			error = err.detail;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export type SkillFile = { path: string; content: string; encoding?: 'base64' };
export type SkillFileSummary = { path: string; size: number; encoding?: 'base64' | null };
export type SkillFileOperation = {
	op: 'put' | 'move' | 'delete';
	path: string;
	content?: string;
	encoding?: 'base64';
	destination?: string;
};

export const skillRequest = async (token: string, path: string, options: RequestInit = {}) => {
	const response = await fetch(`${WEBUI_API_BASE_URL}/skills${path}`, {
		...options,
		headers: {
			authorization: `Bearer ${token}`,
			...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
			...options.headers
		}
	});
	if (!response.ok) {
		const body = await response.json();
		const detail = body.detail ?? body;
		if (response.status === 409 && path.startsWith('/packages')) throw { code: 'version_conflict', detail };
		throw detail;
	}
	return response;
};
export const getSkillFiles = async (token: string, id: string, versionId: string) =>
	(
		await skillRequest(token, `/id/${id}/files?${new URLSearchParams({ version_id: versionId })}`)
	).json();
export const getSkillFile = async (token: string, id: string, versionId: string, path: string) =>
	(
		await skillRequest(
			token,
			`/id/${id}/files/content?${new URLSearchParams({ version_id: versionId, path })}`
		)
	).blob();
export const getSkillHistory = async (token: string, id: string, page = 1) =>
	(await skillRequest(token, `/id/${id}/history?page=${page}`)).json();
export const getSkillVersion = async (token: string, id: string, versionId: string) =>
	(await skillRequest(token, `/id/${id}/history/${versionId}`)).json();
export const deleteSkillHistoryVersion = async (token: string, id: string, versionId: string) =>
	(await skillRequest(token, `/id/${id}/history/${versionId}`, { method: 'DELETE' })).json();
export const setProductionSkillVersion = async (
	token: string,
	id: string,
	versionId: string,
	expectedVersionId: string
) =>
	(
		await skillRequest(token, `/id/${id}/update/version`, {
			method: 'POST',
			body: JSON.stringify({ version_id: versionId, expected_version_id: expectedVersionId })
		})
	).json();
export const cloneSkill = async (
	token: string,
	id: string,
	name: string,
	newId: string,
	versionId?: string
) =>
	(
		await skillRequest(token, `/id/${id}/clone`, {
			method: 'POST',
			body: JSON.stringify({ id: newId, name, version_id: versionId })
		})
	).json();
export const exportSkillBundle = async (
	token: string,
	format: 'json' | 'zip' | 'skill',
	ids: string[] = [],
	versionId?: string
) => {
	const query = new URLSearchParams({ format });
	ids.forEach((id) => query.append('ids', id));
	if (versionId) query.set('version_id', versionId);
	if (format === 'json') return (await skillRequest(token, `/export?${query}`)).blob();
	if (ids.length === 1) {
		const packageQuery = new URLSearchParams({ id: ids[0], format });
		if (versionId) packageQuery.set('version_id', versionId);
		return (await skillRequest(token, `/packages/export?${packageQuery}`)).blob();
	}
	const { default: JSZip } = await import('jszip');
	const packages = await (await skillRequest(token, '/export?format=json')).json();
	const archive = new JSZip();
	const selected = (Array.isArray(packages) ? packages : [packages])
		.filter((skill) => !ids.length || ids.includes(skill.id))
		.sort((a, b) => a.id < b.id ? -1 : a.id > b.id ? 1 : 0);
	for (const skill of selected) {
		for (const file of skill.files) archive.file(`${skill.id}/${file.path}`, file.content, { base64: file.encoding === 'base64' });
	}
	const comment = 'openwebui-skill-package-v1\n' + JSON.stringify(selected.map((skill) => ({
		name: skill.name, description: skill.description, meta: skill.meta, is_active: skill.is_active ?? true
	})));
	if (new TextEncoder().encode(comment).length > 65535) throw new Error('导出元数据超过 ZIP 注释容量，请分批导出或使用 JSON');
	return archive.generateAsync({ type: 'blob', compression: 'DEFLATE', comment });
};
export const importSkillBundles = async (token: string, files: File[], decisions?: object[]) => {
	const body = new FormData();
	const packages = await previewSkillPackages(token, files);
	body.append('files', new Blob([JSON.stringify(packages)], { type: 'application/json' }), 'skills.json');
	if (decisions) body.append('decisions', JSON.stringify(decisions));
	return (
		await skillRequest(token, decisions ? '/import' : '/import/preview', { method: 'POST', body })
	).json();
};
export const loadSkillByUrl = async (token: string, url: string) =>
	(
		await skillRequest(token, '/load/url', {
			method: 'POST',
			body: JSON.stringify({ url })
		})
	).json();
export const skillError = (error: unknown): string => {
	if (error instanceof Error) return error.message;
	if (typeof error === 'string') return error;
	if (error && typeof error === 'object' && 'detail' in error) return skillError(error.detail);
	return JSON.stringify(error) ?? '未知错误';
};

export const downloadSkillBlob = (blob: Blob, filename: string) => {
	const url = URL.createObjectURL(blob);
	const anchor = document.createElement('a');
	anchor.href = url;
	anchor.download = filename;
	document.body.appendChild(anchor);
	anchor.click();
	anchor.remove();
	setTimeout(() => URL.revokeObjectURL(url), 1000);
};

export type SkillBinding = {
	id: string;
	name: string;
	mode: 'assistant' | 'project';
	write_access: boolean;
	bound: boolean;
	inherited: boolean;
	source_id?: string | null;
	project_id?: string | null;
	terminal_id?: string | null;
};

export const getSkillBindings = async (token: string, skillId: string): Promise<{ items: SkillBinding[] }> => {
	const response = await fetch(`${WEBUI_API_BASE_URL}/folders/skill-bindings?${new URLSearchParams({ skill_id: skillId })}`, {
		headers: { authorization: `Bearer ${token}` }
	});
	if (!response.ok) {
		const body = await response.json();
		throw body.detail ?? body;
	}
	return response.json();
};

export const setSkillBinding = async (token: string, folderId: string, skillId: string, enabled: boolean) => {
	const response = await fetch(`${WEBUI_API_BASE_URL}/folders/${encodeURIComponent(folderId)}/skill-binding`, {
		method: 'POST',
		headers: { authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
		body: JSON.stringify({ skill_id: skillId, enabled })
	});
	if (!response.ok) {
		const body = await response.json();
		throw body.detail ?? body;
	}
	return response.json();
};

export type SkillPackageContext = {
	source?: 'workspace' | 'terminal';
	terminal_id?: string;
	project_id?: string;
	chat_id?: string;
};

export const skillPackageQuery = (context: SkillPackageContext = {}, values: Record<string, string> = {}) => {
	const query = new URLSearchParams(values);
	for (const key of ['source', 'terminal_id', 'project_id', 'chat_id'] as const) {
		if (context[key]) query.set(key, context[key]!);
	}
	return query;
};

export const skillPackageEditUrl = (id: string, context: SkillPackageContext = {}) =>
	`/workspace/skills/edit?${skillPackageQuery(context, { id })}`;

export const skillPackageCreateUrl = (context: SkillPackageContext = {}) =>
	`/workspace/skills/create?${skillPackageQuery(context)}`;

export const listSkillPackages = async (token: string, context: SkillPackageContext = {}, query = '', signal?: AbortSignal) =>
	(await skillRequest(token, `/packages?${skillPackageQuery(context, query ? { query } : {})}`, { signal })).json();

export const getSkillPackage = async (token: string, id: string, context: SkillPackageContext = {}) =>
	(await skillRequest(token, `/packages/detail?${skillPackageQuery(context, { id })}`)).json();

export const createSkillPackage = async (token: string, skill: object, context: SkillPackageContext = {}) =>
	(await skillRequest(token, `/packages?${skillPackageQuery(context)}`, { method: 'POST', body: JSON.stringify(skill) })).json();

export const updateSkillPackage = async (token: string, id: string, skill: object, context: SkillPackageContext = {}) =>
	(await skillRequest(token, `/packages?${skillPackageQuery(context, { id })}`, { method: 'PUT', body: JSON.stringify(skill) })).json();

export const deleteSkillPackage = async (token: string, id: string, versionId: string, context: SkillPackageContext = {}) =>
	(await skillRequest(token, `/packages?${skillPackageQuery(context, { id, expected_version_id: versionId })}`, { method: 'DELETE' })).json();

export const exportSkillPackage = async (token: string, id: string, format: 'json' | 'zip' | 'skill', context: SkillPackageContext = {}) =>
	(await skillRequest(token, `/packages/export?${skillPackageQuery(context, { id, format })}`)).blob();

export const previewSkillPackages = async (token: string, files: File[]) => {
	const body = new FormData();
	files.forEach((file) => body.append('files', file, file.webkitRelativePath || file.name));
	return (await skillRequest(token, '/packages/import/preview', { method: 'POST', body })).json();
};

export const skillFileBlob = (file: SkillFile) => new Blob([
	file.encoding === 'base64' ? Uint8Array.from(atob(file.content), (character) => character.charCodeAt(0)) : file.content
]);
