import React, { useState, useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { toast } from 'sonner';
import { Database, CheckCircle2, XCircle, Plus, TestTubeDiagonal, Trash2, Share2 } from 'lucide-react';
import { useDatasources } from '@/features/datasource/hooks/useDatasources';
import type { DatasourceCreatePayload } from '@/features/datasource/api/weaverDatasourceApi';
import { datasourceFormSchema, type DatasourceFormValues } from '@/features/datasource/schemas/datasourceFormSchema';
import { SchemaExplorer } from '@/features/datasource/components/SchemaExplorer';
import { SyncProgress } from '@/features/datasource/components/SyncProgress';
import { ERDiagramPanel } from '@/features/datasource/components/ERDiagramPanel';
import { Input } from '@/components/ui/input';
import { ErrorState } from '@/shared/components/ErrorState';
import { EmptyState } from '@/shared/components/EmptyState';
import { ListSkeleton } from '@/shared/components/ListSkeleton';

/** 데이터소스별 연결 테스트 결과 (인라인 표시용) */
type TestResult = { status: 'ok' | 'fail'; message: string };

/** 하단 탭 타입: 스키마 탐색 또는 ERD 시각화 */
type BottomTab = 'schema' | 'erd';

/** 데이터소스 관리 페이지. Weaver API 연동. */
export const DatasourcePage: React.FC = () => {
 const { datasources, engineTypes, loading, error, refetch, addDatasource, removeDatasource, test } = useDatasources();
 const [testResultByDs, setTestResultByDs] = useState<Record<string, TestResult>>({});
 const [selectedDsName, setSelectedDsName] = useState<string | null>(null);
 const [bottomTab, setBottomTab] = useState<BottomTab>('schema');

 const {
 register,
 handleSubmit,
 reset,
 setValue,
 formState: { errors, isSubmitting },
 } = useForm<DatasourceFormValues>({
 resolver: zodResolver(datasourceFormSchema),
 defaultValues: {
 name: '',
 engine: engineTypes[0]?.engine ?? 'postgres',
 host: '',
 port: '5432',
 database: '',
 user: '',
 password: '',
 },
 });

 useEffect(() => {
 if (engineTypes.length > 0) setValue('engine', engineTypes[0].engine);
 }, [engineTypes, setValue]);

 const handleCreate = async (data: DatasourceFormValues) => {
 const payload: DatasourceCreatePayload = {
 name: data.name.trim(),
 engine: data.engine,
 connection: {
 host: data.host,
 port: parseInt(data.port, 10),
 database: data.database,
 user: data.user,
 password: data.password,
 },
 };
 try {
 await addDatasource(payload);
 reset({
 name: '',
 engine: engineTypes[0]?.engine ?? 'postgres',
 host: '',
 port: '5432',
 database: '',
 user: '',
 password: '',
 });
 toast.success('데이터소스가 추가되었습니다.');
 } catch (err) {
 console.error('Create datasource failed', err);
 toast.error('데이터소스 추가에 실패했습니다.');
 }
 };

 const handleTest = async (dsName: string) => {
 setTestResultByDs((prev) => ({ ...prev, [dsName]: { status: 'ok', message: '확인 중…' } }));
 try {
 const res = await test(dsName);
 const ok = !!(res as any).success;
 setTestResultByDs((prev) => ({
 ...prev,
 [dsName]: { status: ok ? 'ok' : 'fail', message: ok ? '연결 성공' : (res as any).message ?? '연결 실패' },
 }));
 if (ok) toast.success('데이터소스 연결 테스트에 성공했습니다.');
 else toast.error('데이터소스 연결 테스트에 실패했습니다.');
 } catch (err) {
 const msg = err instanceof Error ? err.message : '연결 실패';
 setTestResultByDs((prev) => ({ ...prev, [dsName]: { status: 'fail', message: msg } }));
 toast.error('데이터소스 연결 테스트에 실패했습니다.');
 }
 };

 const handleDelete = async (dsName: string) => {
 try {
 await removeDatasource(dsName);
 toast.success('데이터소스가 삭제되었습니다.');
 } catch (err) {
 console.error('Delete datasource failed', err);
 toast.error('데이터소스 삭제에 실패했습니다.');
 }
 };

 if (loading) {
 return (
 <div className="px-4 md:px-8 lg:px-12 py-4 md:py-8 space-y-6">
 <h1 className="text-2xl md:text-4xl lg:text-5xl font-semibold tracking-tight text-foreground font-heading">데이터리소스</h1>
 <ListSkeleton rows={6} className="max-w-2xl" />
 </div>
 );
 }
 if (error) {
 return (
 <div className="px-4 md:px-8 lg:px-12 py-4 md:py-8 space-y-6">
 <h1 className="text-2xl md:text-4xl lg:text-5xl font-semibold tracking-tight text-foreground font-heading">데이터리소스</h1>
 <ErrorState message={`목록을 불러올 수 없습니다. ${error.message}`} onRetry={refetch} />
 </div>
 );
 }

 return (
 <div className="px-4 md:px-8 lg:px-12 py-4 md:py-8 space-y-6 md:space-y-8 overflow-auto h-full">
 {/* Title Row */}
 <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
 <div className="space-y-1.5">
 <h1 className="text-2xl md:text-4xl lg:text-5xl font-semibold tracking-tight text-foreground font-heading">데이터리소스</h1>
 <p className="text-[12px] md:text-[13px] text-muted-foreground font-mono">
 데이터베이스 연결을 설정하고 스키마를 관리합니다
 </p>
 </div>
 <button
 type="button"
 className="flex items-center gap-2 px-4 py-2.5 bg-destructive text-primary-foreground text-[12px] font-medium font-heading rounded hover:bg-red-700 transition-colors"
 onClick={() => document.getElementById('ds-form')?.scrollIntoView({ behavior: 'smooth' })}
 >
 <Plus className="h-3.5 w-3.5" />
 신규 등록
 </button>
 </div>

 {/* Creation Form */}
 <form
 id="ds-form"
 onSubmit={handleSubmit(handleCreate)}
 className="space-y-6"
 >
 <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-5">
 {/* Left column — 주요 정보 */}
 <div className="space-y-5">
 <span className="text-[11px] font-semibold text-foreground/60 font-mono uppercase tracking-wider">주요 정보</span>
 <FormField label="이름" error={errors.name?.message}>
 <Input
 {...register('name')}
 placeholder="DynamoDB_db"
 className="bg-card border-border text-foreground placeholder:text-foreground/60 font-mono text-[13px]"
 />
 </FormField>
 <FormField label="엔진">
 <select
 aria-label="엔진"
 {...register('engine')}
 className="h-9 w-full rounded border border-border bg-card px-3 text-[13px] text-foreground font-mono"
 >
 {engineTypes.length ? engineTypes.map((t) => <option key={t.engine} value={t.engine}>{t.engine}</option>) : <option value="postgres">postgres</option>}
 </select>
 </FormField>
 <div className="grid grid-cols-2 gap-4">
 <FormField label="호스트" error={errors.host?.message}>
 <Input
 {...register('host')}
 placeholder="localhost"
 className="bg-card border-border text-foreground placeholder:text-foreground/60 font-mono text-[13px]"
 />
 </FormField>
 <FormField label="포트" error={errors.port?.message}>
 <Input
 {...register('port')}
 placeholder="5432"
 className="bg-card border-border text-foreground placeholder:text-foreground/60 font-mono text-[13px]"
 />
 </FormField>
 </div>
 </div>

 {/* Right column — 연결 */}
 <div className="space-y-5">
 <span className="text-[11px] font-semibold text-foreground/60 font-mono uppercase tracking-wider">연결</span>
 <FormField label="사용자명" error={errors.user?.message}>
 <Input
 {...register('user')}
 placeholder="user"
 className="bg-card border-border text-foreground placeholder:text-foreground/60 font-mono text-[13px]"
 />
 </FormField>
 <FormField label="비밀번호" error={errors.password?.message}>
 <Input
 type="password"
 {...register('password')}
 placeholder="••••••••"
 className="bg-card border-border text-foreground placeholder:text-foreground/60 font-mono text-[13px]"
 />
 </FormField>
 </div>
 </div>

 {/* Database + submit */}
 <div className="space-y-4">
 <FormField label="데이터베이스" error={errors.database?.message}>
 <Input
 {...register('database')}
 placeholder="$INSTANCE_db"
 className="bg-card border-border text-foreground placeholder:text-foreground/60 font-mono text-[13px] max-w-md"
 />
 </FormField>
 <button
 type="submit"
 disabled={isSubmitting}
 className="flex items-center gap-2 px-4 py-2.5 bg-destructive text-primary-foreground text-[12px] font-medium font-heading rounded hover:bg-red-700 transition-colors disabled:opacity-50"
 >
 <Plus className="h-3.5 w-3.5" />
 생성
 </button>
 </div>
 </form>

 {/* Datasource List Table */}
 <div className="space-y-4">
 <div className="flex items-center justify-between">
 <h2 className="text-sm font-semibold text-foreground font-heading">데이터리소스 목록</h2>
 <button
 type="button"
 className="flex items-center gap-2 px-3 py-1.5 text-[12px] text-muted-foreground border border-border rounded hover:bg-muted transition-colors"
 >
 <TestTubeDiagonal className="h-3.5 w-3.5" />
 테스트
 </button>
 </div>

 {datasources.length === 0 ? (
 <EmptyState
 icon={Database}
 title="등록된 데이터소스가 없습니다"
 description="위 폼에서 연결 정보를 입력한 뒤 추가하면 스키마 탐색과 동기화를 사용할 수 있습니다."
 />
 ) : (
 <div className="border border-border rounded overflow-x-auto">
 {/* Table header */}
 <div className="grid grid-cols-[1fr_100px_100px_100px_80px_100px] min-w-[640px] bg-muted px-5 py-3">
 <span className="text-[11px] font-medium text-foreground/60 font-mono uppercase">Name</span>
 <span className="text-[11px] font-medium text-foreground/60 font-mono uppercase">Type</span>
 <span className="text-[11px] font-medium text-foreground/60 font-mono uppercase">Status</span>
 <span className="text-[11px] font-medium text-foreground/60 font-mono uppercase">Tables</span>
 <span className="text-[11px] font-medium text-foreground/60 font-mono uppercase">Test</span>
 <span className="text-[11px] font-medium text-foreground/60 font-mono uppercase">Actions</span>
 </div>

 {/* Table rows */}
 {datasources.map((ds) => {
 const testResult = testResultByDs[ds.name];
 const isSelected = selectedDsName === ds.name;
 const statusOk = (ds.status || '').toLowerCase() === 'connected' || (ds.status || '').toLowerCase() === 'ok';
 return (
 <div
 key={ds.name}
 className={`grid grid-cols-[1fr_100px_100px_100px_80px_100px] min-w-[640px] items-center px-5 py-3 border-t border-border transition-colors ${
 isSelected ? 'bg-red-50' : 'hover:bg-background'
 }`}
 >
 <button
 type="button"
 onClick={() => setSelectedDsName((prev) => (prev === ds.name ? null : ds.name))}
 className="text-[13px] font-medium text-foreground font-heading text-left truncate hover:text-destructive transition-colors"
 >
 {ds.name}
 </button>
 <span className="text-[13px] text-muted-foreground font-mono">{ds.engine}</span>
 <span className={`text-[11px] font-medium ${statusOk ? 'text-green-600' : 'text-destructive'}`}>
 {ds.status ?? 'unknown'}
 </span>
 <span className="text-[13px] text-muted-foreground font-mono">—</span>
 <div>
 {testResult && (
 <span className={`flex items-center gap-1 text-xs ${testResult.status === 'ok' ? 'text-green-600' : 'text-destructive'}`}>
 {testResult.status === 'ok' ? <CheckCircle2 size={12} /> : <XCircle size={12} />}
 </span>
 )}
 </div>
 <div className="flex items-center gap-2">
 <button
 type="button"
 onClick={() => handleTest(ds.name)}
 className="text-[11px] text-muted-foreground hover:text-foreground transition-colors underline"
 >
 test
 </button>
 <button
 type="button"
 onClick={() => handleDelete(ds.name)}
 title="삭제"
 className="text-[11px] text-destructive hover:text-destructive transition-colors"
 >
 <Trash2 className="h-3 w-3" />
 </button>
 </div>
 </div>
 );
 })}
 </div>
 )}
 </div>

 {/* Bottom section: 탭 (스키마 | ERD) + Sync */}
 <div className="space-y-4 pb-8">
 {/* 탭 헤더 */}
 <div className="flex items-center gap-1 border-b border-border">
  <button
   type="button"
   onClick={() => setBottomTab('schema')}
   className={`px-4 py-2.5 text-[12px] font-heading transition-colors ${
    bottomTab === 'schema'
     ? 'text-foreground font-semibold border-b-2 border-red-600'
     : 'text-foreground/60 hover:text-muted-foreground'
   }`}
  >
   스키마 탐색
  </button>
  <button
   type="button"
   onClick={() => setBottomTab('erd')}
   className={`flex items-center gap-1.5 px-4 py-2.5 text-[12px] font-heading transition-colors ${
    bottomTab === 'erd'
     ? 'text-foreground font-semibold border-b-2 border-red-600'
     : 'text-foreground/60 hover:text-muted-foreground'
   }`}
  >
   <Share2 className="h-3 w-3" />
   ERD
  </button>
 </div>

 {/* 탭 컨텐츠 */}
 {bottomTab === 'schema' ? (
  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
   <div className="space-y-3">
    <h3 className="text-sm font-semibold text-foreground font-heading">데이터매핑 관리</h3>
    <SchemaExplorer
     selectedDsName={selectedDsName}
     onSelectDs={(name) => setSelectedDsName(name || null)}
     datasourceNames={datasources.map((d) => d.name)}
    />
   </div>
   <div className="space-y-3">
    <h3 className="text-sm font-semibold text-foreground font-heading">스키마 관리</h3>
    <SyncProgress selectedDsName={selectedDsName} onComplete={refetch} />
   </div>
  </div>
 ) : (
  <div className="border border-border rounded-lg overflow-hidden" style={{ minHeight: 480 }}>
   {selectedDsName ? (
    <ERDiagramPanel datasourceId={selectedDsName} />
   ) : (
    <div className="flex flex-col items-center justify-center h-full min-h-[480px] text-foreground/60 gap-3">
     <Share2 className="h-8 w-8 opacity-30" />
     <p className="text-sm">데이터소스를 선택하면 ERD 다이어그램이 표시됩니다.</p>
     <p className="text-xs">위 목록에서 데이터소스 이름을 클릭하세요.</p>
    </div>
   )}
  </div>
 )}
 </div>
 </div>
 );
};

// ---------------------------------------------------------------------------
// Form field helper
// ---------------------------------------------------------------------------

function FormField({
 label,
 error,
 children,
}: {
 label: string;
 error?: string;
 children: React.ReactNode;
}) {
 return (
 <div className="space-y-1.5">
 <label className="text-[11px] font-medium text-foreground/60 font-mono uppercase">{label}</label>
 {children}
 {error && <span className="text-[11px] text-destructive">{error}</span>}
 </div>
 );
}
