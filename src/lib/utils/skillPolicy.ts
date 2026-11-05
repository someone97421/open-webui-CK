export type SkillMode = 'chat' | 'assistant' | 'project';
export type AttachmentDelta = { added: string[]; removed: string[] };
export type AttachmentOverrides = {
	version: 1;
	skills: AttachmentDelta;
	tools: AttachmentDelta;
};
export type AttachmentPolicy = {
	mode: SkillMode;
	capabilities: Record<string, boolean>;
	terminalAvailable: boolean;
	skillSources?: Record<string, string>;
	projectId?: string | null;
	terminalId?: string | null;
	toolSources?: Record<string, string>;
};
export const defaultAttachmentPolicy: AttachmentPolicy = {
	mode: 'chat', capabilities: {}, terminalAvailable: false
};

export const skillAvailable = (
	skill: any,
	mode: SkillMode,
	capabilities: Record<string, boolean> = {},
	terminalAvailable = true
): boolean => {
	if (!skill || skill.is_active === false) return false;
	const meta = skill.meta ?? {};
	if ((meta.modes ?? skill.modes)?.[mode] === false) return false;
	const requires = meta.requires ?? skill.requires ?? [];
	return requires.every((name: string) =>
		name === 'terminal' ? terminalAvailable && capabilities.terminal !== false : capabilities[name] !== false
	) && (skill.source !== 'terminal' || (terminalAvailable && capabilities.terminal !== false));
};

export const toolAvailable = (tool: any, capabilities: Record<string, boolean> = {}) => {
	if (!tool || tool.is_active === false) return false;
	if (tool.id?.startsWith('direct_server:')) return capabilities.tool_servers !== false && capabilities.direct_tool_servers !== false;
	return tool.id?.startsWith('server:') ? capabilities.tool_servers !== false : capabilities.tools !== false;
};

const ids = (value: unknown): string[] => Array.isArray(value)
	? [...new Set(value.filter((id): id is string => typeof id === 'string' && id.length > 0))] : [];
export const attachmentOverrides = (value?: any, legacy?: any): AttachmentOverrides => ({
	version: 1,
	skills: { added: ids(value?.skills?.added ?? legacy?.selectedSkillIds), removed: ids(value?.skills?.removed) },
	tools: { added: ids(value?.tools?.added ?? legacy?.selectedToolIds), removed: ids(value?.tools?.removed) }
});
export const effectiveAttachments = (defaults: string[], delta: AttachmentDelta) =>
	[...new Set([...defaults, ...delta.added])].filter((id) => !delta.removed.includes(id));
export const updateAttachmentDelta = (delta: AttachmentDelta, previous: string[], next: string[]): AttachmentDelta => {
	const added = next.filter((id) => !previous.includes(id));
	const removed = previous.filter((id) => !next.includes(id));
	return {
		added: [...new Set([...delta.added.filter((id) => !removed.includes(id)), ...added])],
		removed: [...new Set([...delta.removed.filter((id) => !added.includes(id)), ...removed])]
	};
};

export const scopedSkills = (globalItems: any[] = [], terminalItems: any[] = []) =>
	[...new Map([...globalItems, ...terminalItems].map((skill) => [skill.id, skill])).values()];

export const canonicalSkillId = (id: string, catalog: any[]) => {
	if (catalog.some((skill) => skill.id === id)) return id;
	const matches = catalog.filter((skill) => skill.source === 'terminal' &&
		(id === skill.name || id === `terminal:${skill.name}` ||
			id === `terminal:${encodeURIComponent(skill.name)}` || (skill.aliases ?? []).includes(id)));
	return matches[0]?.id ?? id;
};
export const canonicalSkillIds = (values: string[], catalog: any[]): string[] =>
	[...new Set(values.map((id) => canonicalSkillId(id, catalog)))];

export const attachmentCapabilities = (models: any[], config: any, user: any, mode: SkillMode) => {
	const capabilities: Record<string, boolean> = {};
	for (const model of models) {
		for (const [name, enabled] of Object.entries(model?.info?.meta?.capabilities ?? {})) {
			if (enabled === false) capabilities[name] = false;
		}
	}
	for (const name of ['web_search', 'image_generation', 'code_interpreter']) {
		if (config?.features?.[`enable_${name}`] === false ||
			(user?.role !== 'admin' && user?.permissions?.features?.[name] === false)) capabilities[name] = false;
	}
	if (mode === 'project') capabilities.code_interpreter = false;
	if (config?.features?.enable_tools === false) capabilities.tools = false;
	if (config?.features?.enable_direct_integrations === false ||
		(user?.role !== 'admin' && user?.permissions?.features?.direct_tool_servers === false)) capabilities.direct_tool_servers = false;
	if (config?.features?.enable_tool_servers === false) {
		capabilities.tool_servers = false;
		capabilities.terminal = false;
	}
	return capabilities;
};

export const runtimeAttachmentCapabilities = (
	models: any[], config: any, user: any, mode: SkillMode,
	features: Record<string, boolean>, params: Record<string, any>, sessionAvailable: boolean,
	noteChat = false
) => {
	const capabilities = attachmentCapabilities(models, config, user, mode);
	const native = (model: any) => noteChat || (sessionAvailable &&
		(params.function_calling ?? model?.info?.params?.function_calling) !== 'legacy' &&
		model?.info?.meta?.capabilities?.builtin_tools !== false);
	capabilities.builtin_tools = models.length > 0 && models.every(native);
	for (const name of ['web_search', 'image_generation', 'code_interpreter']) {
		capabilities[name] = capabilities[name] !== false && features[name] === true &&
			models.every((model) => !native(model) || model?.info?.meta?.builtinTools?.[name] !== false);
	}
	return capabilities;
};
