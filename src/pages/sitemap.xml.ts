import type { APIRoute } from 'astro';
import { getCollection } from 'astro:content';
import { summary } from '../lib/data';

const SITE = 'https://ann1678.com';

export const GET: APIRoute = async () => {
  // 実況と記録は1時間ごとに書き換わる。エンジンが書いた時刻をそのまま lastmod にする。
  const live = summary?.generated_at ? new Date(summary.generated_at).toISOString() : new Date().toISOString();
  const posts = await getCollection('posts', ({ data }) => !data.draft);
  const urls = [
    { loc: '/', priority: '1.0', changefreq: 'hourly', lastmod: live },
    { loc: '/record/', priority: '0.9', changefreq: 'hourly', lastmod: live },
    { loc: '/method/', priority: '0.8', changefreq: 'monthly' },
    { loc: '/posts/', priority: '0.6', changefreq: 'weekly' },
    { loc: '/about/', priority: '0.5', changefreq: 'monthly' },
    ...posts.map((p) => ({
      loc: `/posts/${p.id}/`,
      priority: '0.6',
      changefreq: 'monthly',
      lastmod: p.data.date.toISOString(),
    })),
  ];
  const body = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls.map((u) => `  <url>
    <loc>${SITE}${u.loc}</loc>${'lastmod' in u && u.lastmod ? `
    <lastmod>${u.lastmod}</lastmod>` : ''}
    <changefreq>${u.changefreq}</changefreq>
    <priority>${u.priority}</priority>
  </url>`).join('\n')}
</urlset>
`;
  return new Response(body, { headers: { 'Content-Type': 'application/xml; charset=utf-8' } });
};
