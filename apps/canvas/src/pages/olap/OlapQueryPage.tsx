export const OlapQueryPage = () => {
    return (
        <div className="space-y-6">
            <h1 className="text-2xl font-bold">OLAP Pivot</h1>
            <p className="text-neutral-400">Drag and drop dimensions and measures to analyze your data.</p>
            <div className="flex gap-4 h-[600px]">
                {/* Sidebar Palette */}
                <div className="w-64 bg-neutral-900 border border-neutral-800 rounded p-4 flex flex-col space-y-4">
                    <h3 className="font-semibold border-b border-neutral-800 pb-2">Dimensions</h3>
                    <div className="p-2 bg-neutral-800 rounded text-sm text-neutral-300">Department</div>
                    <div className="p-2 bg-neutral-800 rounded text-sm text-neutral-300">Quarter</div>

                    <h3 className="font-semibold border-b border-neutral-800 pb-2 mt-4">Measures</h3>
                    <div className="p-2 bg-neutral-800 rounded text-sm text-neutral-300">Revenue</div>
                    <div className="p-2 bg-neutral-800 rounded text-sm text-neutral-300">Cost</div>
                </div>

                {/* Main Pivot Area */}
                <div className="flex-1 bg-neutral-900 border border-neutral-800 rounded p-4 flex items-center justify-center text-neutral-500">
                    Drop dimensions and measures to build a pivot table
                </div>
            </div>
        </div>
    );
};
