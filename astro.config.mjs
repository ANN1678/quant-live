// @ts-check
import { defineConfig } from 'astro/config';


export default defineConfig({
  site: 'https://ann1678.com',
  trailingSlash: 'always',
  build: { format: 'directory' },
  devToolbar: { enabled: false },
});
