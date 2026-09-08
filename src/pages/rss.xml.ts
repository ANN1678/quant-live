import type { APIRoute } from 'astro';
import { getCollection } from 'astro:content';

const SITE = 'https://ann1678.com';
const esc = (s: string) =>
  s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

export const GET: APIRoute = async () => {
  const posts = (await getCollection('posts', ({ data }) => !data.draft))
    .sort((a, b) => b.data.date.valueOf() - a.data.date.valueOf());

  const items = posts.map((p) => `    <item>
      <title>${esc(p.data.title)}</title>
      <link>${SITE}/posts/${p.id}/</link>
      <guid isPermaLink="true">${SITE}/posts/${p.id}/</guid>
      <pubDate>${p.data.date.toUTCString()}</pubDate>${p.data.summary ? `
      <description>${esc(p.data.summary)}</description>` : ''}
    </item>`).join('\n');

  const body = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>クオンツ実況の手記</title>
    <link>${SITE}/posts/</link>
    <atom:link href="${SITE}/rss.xml" rel="self" type="application/rss+xml" />
    <description>相場の予測と仮想売買の記録から、数字だけでは残らないことを書いています。株式会社ANN。</description>
    <language>ja</language>
    <lastBuildDate>${new Date().toUTCString()}</lastBuildDate>
${items}
  </channel>
</rss>
`;
  return new Response(body, { headers: { 'Content-Type': 'application/rss+xml; charset=utf-8' } });
};
