import { listSkillPackages } from '$lib/apis/skills';
import type { AttachmentPolicy } from '$lib/utils/skillPolicy';

export const loadSkillCatalog = (token: string, policy: Partial<AttachmentPolicy> = {}, query = '') =>
	listSkillPackages(token, policy.mode === 'project' && policy.projectId && policy.capabilities?.terminal !== false
		? { project_id: policy.projectId, ...(policy.terminalId ? { terminal_id: policy.terminalId } : {}) }
		: {}, query);
