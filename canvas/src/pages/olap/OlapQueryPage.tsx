export const OlapQueryPage = () => {
 return (
 <div className="space-y-6">
 <h1 className="text-2xl font-bold">OLAP Pivot</h1>
 <p className="text-muted-foreground">Drag and drop dimensions and measures to analyze your data.</p>
 <div className="flex gap-4 h-[600px]">
 {/* Sidebar Palette */}
 <div className="w-64 bg-card border border-border rounded p-4 flex flex-col space-y-4">
 <h3 className="font-semibold border-b border-border pb-2">Dimensions</h3>
 <div className="p-2 bg-muted rounded text-sm text-foreground/80">Department</div>
 <div className="p-2 bg-muted rounded text-sm text-foreground/80">Quarter</div>

 <h3 className="font-semibold border-b border-border pb-2 mt-4">Measures</h3>
 <div className="p-2 bg-muted rounded text-sm text-foreground/80">Revenue</div>
 <div className="p-2 bg-muted rounded text-sm text-foreground/80">Cost</div>
 </div>

 {/* Main Pivot Area */}
 <div className="flex-1 bg-card border border-border rounded p-4 flex items-center justify-center text-foreground0">
 Drop dimensions and measures to build a pivot table
 </div>
 </div>
 </div>
 );
};
