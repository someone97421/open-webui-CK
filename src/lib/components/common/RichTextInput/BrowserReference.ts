import { Node } from '@tiptap/core';
import type { BrowserReference } from '$lib/utils/browserSidebar';

export const browserReferenceNodeName = 'browserReference';
const referenceAttribute = 'data-browser-reference';
const labels = { page: '网页引用', selection: '网页选文', element: '网页元素' };

export function readBrowserReference(element: Element): BrowserReference | null {
	const encoded = element.getAttribute(referenceAttribute);
	if (!encoded) return null;
	try {
		const reference: BrowserReference = JSON.parse(decodeURIComponent(encoded));
		if (
			reference &&
			Object.hasOwn(labels, reference.kind) &&
			Number.isSafeInteger(reference.tabId) &&
			typeof reference.title === 'string' &&
			typeof reference.url === 'string' &&
			typeof reference.preview === 'string' &&
			typeof reference.text === 'string' &&
			reference.text
		) {
			return reference;
		}
	} catch {
		return null;
	}
	return null;
}

const buttonFocus = 'focus-visible:outline focus-visible:outline-2 focus-visible:outline-current';

export default Node.create({
	name: browserReferenceNodeName,
	group: 'inline',
	inline: true,
	atom: true,
	addAttributes() {
		return { reference: { default: null, rendered: false } };
	},
	parseHTML() {
		return [{
			tag: `span[${referenceAttribute}]`,
			getAttrs: (element) => {
				const reference = readBrowserReference(element);
				return reference ? { reference } : false;
			}
		}];
	},
	renderHTML({ node }) {
		const reference: BrowserReference = node.attrs.reference;
		return ['span', { [referenceAttribute]: encodeURIComponent(JSON.stringify(reference)) }, reference?.text ?? ''];
	},
	renderText({ node }) {
		return node.attrs.reference?.text ?? '';
	},
	addNodeView() {
		return ({ node, editor, getPos }) => {
			const reference: BrowserReference | null = node.attrs.reference;
			const dom = document.createElement('span');
			dom.contentEditable = 'false';
			if (!reference) return { dom };

			const kind = labels[reference.kind];
			const title = reference.title || reference.url;
			dom.className = 'not-prose inline-flex max-w-full items-center gap-0.5 align-middle rounded-md border border-gray-200 bg-gray-50 text-xs dark:border-gray-700 dark:bg-gray-800';

			const preview = document.createElement('button');
			preview.type = 'button';
			preview.className = `min-w-0 max-w-72 truncate rounded-md px-2 py-1 text-start hover:bg-gray-200 dark:hover:bg-gray-700 ${buttonFocus}`;
			preview.textContent = `${kind} · ${title}`;
			preview.title = preview.textContent;
			preview.setAttribute('aria-haspopup', 'dialog');
			dom.append(preview);

			const remove = document.createElement('button');
			remove.type = 'button';
			remove.className = `shrink-0 rounded-md px-1.5 py-1 hover:bg-gray-200 dark:hover:bg-gray-700 ${buttonFocus}`;
			remove.textContent = '×';
			remove.title = `移除${kind}`;
			remove.setAttribute('aria-label', `移除${kind}：${title}`);
			remove.onclick = () => {
				const pos = getPos();
				if (editor.isEditable && typeof pos === 'number') {
					editor.chain().focus().deleteRange({ from: pos, to: pos + node.nodeSize }).run();
				}
			};
			if (editor.isEditable) dom.append(remove);

			let dialog: HTMLDialogElement | undefined;
			preview.onclick = () => {
				if (dialog?.open) return;
				const panel = document.createElement('dialog');
				dialog = panel;
				panel.className = 'm-auto max-h-[80vh] w-[calc(100%-2rem)] max-w-lg overflow-auto rounded-xl bg-white p-4 text-gray-900 shadow-xl backdrop:bg-black/40 dark:bg-gray-900 dark:text-gray-100';
				panel.setAttribute('aria-label', `${kind}预览：${title}`);

				const header = document.createElement('div');
				header.className = 'flex items-start justify-between gap-3';
				const heading = document.createElement('h2');
				heading.className = 'break-words font-medium';
				heading.textContent = `${kind} · ${title}`;
				const close = document.createElement('button');
				close.type = 'button';
				close.className = `shrink-0 rounded-md px-2 hover:bg-gray-100 dark:hover:bg-gray-800 ${buttonFocus}`;
				close.textContent = '关闭';
				close.onclick = () => panel.close();
				header.append(heading, close);

				const content = document.createElement('pre');
				content.className = 'mt-3 whitespace-pre-wrap break-words text-sm';
				content.textContent = reference.preview;
				panel.append(header, content);
				panel.addEventListener('close', () => {
					panel.remove();
					dialog = undefined;
					if (preview.isConnected) preview.focus();
				}, { once: true });
				document.body.append(panel);
				panel.showModal();
				close.focus();
			};

			return {
				dom,
				stopEvent: (event) => event.target === preview || event.target === remove,
				ignoreMutation: () => true,
				destroy: () => dialog?.remove()
			};
		};
	}
});
