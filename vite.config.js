import { resolve } from 'path';
import { defineConfig } from 'vitest/config';

const projectRootDir = resolve(__dirname);

export default defineConfig({
	test: {
		environment: 'jsdom',
        globalSetup: 'frontend/src/test/globalSetup.ts',
        setupFiles: 'frontend/src/test/setup.ts',
        coverage: {
            include: [
                "frontend/src/**/*.ts",
                "frontend/src/**/*.tsx",
            ],
            exclude: [
                "frontend/src/main.tsx",
                "frontend/src/test/*.ts",
                "frontend/src/types/*.ts",
                "frontend/src/**/*.test.ts",
                "frontend/src/**/*.test.tsx",
            ],
            thresholds: {
                branches: 75,
                functions: 75,
                lines: 70,
                statements: 70
            }
        },
	},
	resolve: {
		alias: [
			{
				find: '@dashlive/routemap',
				replacement: resolve(projectRootDir, 'frontend/src/test/fixtures/routemap.js')
			},
			{
				find: '@dashlive/options',
				replacement: resolve(projectRootDir, 'frontend/src/test/fixtures/options.js')
			}
		]
	}
})