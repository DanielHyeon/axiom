import ReactDiffViewer from 'react-diff-viewer-continued';

const diffViewerStyles = {
  variables: {
    dark: {
      diffViewerBackground: '#171717',
      diffViewerColor: '#e5e5e5',
      addedBackground: '#14532d33',
      addedColor: '#bbf7d0',
      removedBackground: '#7f1d1d33',
      removedColor: '#fecaca',
      wordAddedBackground: '#22c55e44',
      wordRemovedBackground: '#ef444444',
    },
  },
};

interface DocumentDiffViewerProps {
  oldValue: string;
  newValue: string;
  splitView?: boolean;
}

/** Side-by-side 또는 unified diff. react-diff-viewer-continued 사용. */
export function DocumentDiffViewer({ oldValue, newValue, splitView = true }: DocumentDiffViewerProps) {
  return (
    <div className="rounded border border-neutral-800 overflow-hidden">
      <ReactDiffViewer
        oldValue={oldValue}
        newValue={newValue}
        splitView={splitView}
        useDarkTheme
        styles={diffViewerStyles}
        leftTitle="원본"
        rightTitle="현재 버전"
        showDiffOnly={false}
      />
    </div>
  );
}
