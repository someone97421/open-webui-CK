export type ProjectData = {
	version: 1;
	terminal_id: string;
	archived: boolean;
};

export type ProjectFolder = {
	id?: string;
	project?: ProjectData;
	data?: {
		project?: ProjectData;
		[key: string]: unknown;
	};
	[key: string]: unknown;
};

export const getFolderProject = (folder: ProjectFolder | null | undefined): ProjectData | null => {
	if (!folder) return null;
	const candidate = folder.data?.project ?? folder.project;
	if (
		!candidate ||
		candidate.version !== 1 ||
		typeof candidate.terminal_id !== 'string' ||
		!candidate.terminal_id
	) {
		return null;
	}
	return {
		version: 1,
		terminal_id: candidate.terminal_id,
		archived: candidate.archived === true
	};
};

export const isProjectFolder = (folder: ProjectFolder | null | undefined) =>
	getFolderProject(folder) !== null;

export const isArchivedProject = (folder: ProjectFolder | null | undefined) =>
	getFolderProject(folder)?.archived ?? false;

export const getProjectTerminalId = (folder: ProjectFolder | null | undefined) =>
	getFolderProject(folder)?.terminal_id ?? null;

export const getAccessibleProjectTerminals = <T extends { id?: string; contexts?: Record<string, unknown> }>(
	servers: T[] | null | undefined
): T[] => (servers ?? []).filter((server) => !!server.id && server.contexts?.project !== false);

export const isCrossProjectChatMove = (
	sourceFolder: ProjectFolder | null | undefined,
	targetFolder: ProjectFolder | null | undefined
) => {
	if (!isProjectFolder(sourceFolder) && !isProjectFolder(targetFolder)) return false;
	return sourceFolder?.id !== targetFolder?.id;
};

export const PROJECT_CHAT_MOVE_ERROR = '项目会话不能跨项目或移至普通会话。';
export const PROJECT_IMPORT_ERROR = '首版项目不支持导入已有会话，请在项目内新建会话。';
