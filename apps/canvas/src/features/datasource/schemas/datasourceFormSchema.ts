import { z } from 'zod';

export const datasourceFormSchema = z.object({
  name: z.string().min(1, '데이터소스 이름을 입력하세요.').regex(/^[a-zA-Z0-9_-]+$/, '이름은 영문, 숫자, _, - 만 사용 가능합니다.'),
  engine: z.string().min(1, '엔진을 선택하세요.'),
  host: z.string().min(1, '호스트를 입력하세요.'),
  port: z.string().min(1, '포트를 입력하세요.').refine((v) => /^\d+$/.test(v) && parseInt(v, 10) <= 65535, '올바른 포트 번호를 입력하세요.'),
  database: z.string().min(1, '데이터베이스명을 입력하세요.'),
  user: z.string().min(1, '사용자명을 입력하세요.'),
  password: z.string().min(1, '비밀번호를 입력하세요.'),
});

export type DatasourceFormValues = z.infer<typeof datasourceFormSchema>;
