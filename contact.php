<?php
/**
 * /contact/ のフォームを受ける。
 *
 * ⚠ 宛先はここにしか書かない。ページ側には出さない（2026-09-12 CEO指示）。
 * ⚠ このファイルは public/ に置く。Astro が dist/ へそのまま写して、deploy ブランチに乗る。
 *    サーバーの public_html は毎回 git reset --hard で戻るので、手で置いたものは消える。
 * ⚠ 送られた中身を画面に出さない。そのまま返すと、他人に踏ませる入口になる。
 */

declare(strict_types=1);

const TO      = 'info@ann1678.com';
const FROM    = 'no-reply@ann1678.com';
const BACK    = '/contact/';
const MAX_PER_HOUR = 5;   // 同じ相手からの上限

mb_internal_encoding('UTF-8');
mb_language('Japanese');

function back(string $q): never {
    header('Location: ' . BACK . $q, true, 303);
    exit;
}

function fail(string $why): never {
    // 何が弾かれたかは外へ出さない。ログにだけ残す。
    error_log('[contact] rejected: ' . $why);
    back('?sent=0');
}

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    back('');
}

// 機械よけ。人には見えない欄が埋まっていたら、そこで捨てる
if (trim((string)($_POST['website'] ?? '')) !== '') {
    fail('honeypot');
}

$name  = trim((string)($_POST['name'] ?? ''));
$email = trim((string)($_POST['email'] ?? ''));
$body  = trim((string)($_POST['body'] ?? ''));

if ($body === '' || mb_strlen($body) < 4) {
    fail('empty body');
}
if (mb_strlen($body) > 4000 || mb_strlen($name) > 80 || mb_strlen($email) > 160) {
    fail('too long');
}
if ($email !== '' && !filter_var($email, FILTER_VALIDATE_EMAIL)) {
    fail('bad address');
}
// 改行を混ぜて宛先を足す手口を断つ
foreach ([$name, $email] as $one) {
    if (preg_match('/[\r\n]/', $one)) {
        fail('header injection');
    }
}

// 同じ相手からの連投を止める。1時間に MAX_PER_HOUR 通まで
$ip   = (string)($_SERVER['REMOTE_ADDR'] ?? 'unknown');
$file = sys_get_temp_dir() . '/ann-contact-' . hash('sha256', $ip) . '.txt';
$now  = time();
$hits = [];
if (is_readable($file)) {
    $hits = array_filter(
        array_map('intval', explode(',', (string)file_get_contents($file))),
        static fn(int $t): bool => $t > $now - 3600
    );
}
if (count($hits) >= MAX_PER_HOUR) {
    fail('rate limit');
}
$hits[] = $now;
@file_put_contents($file, implode(',', $hits), LOCK_EX);

$subject = 'ann1678.com の連絡フォーム';
$lines = [
    '名前　　: ' . ($name  !== '' ? $name  : '（書かれていません）'),
    '返信先　: ' . ($email !== '' ? $email : '（書かれていません）'),
    '送信時刻: ' . date('Y-m-d H:i:s'),
    '送信元　: ' . $ip,
    '',
    '--- 本文 ---',
    $body,
];
$headers = [
    'From: ANN <' . FROM . '>',
    'Reply-To: ' . ($email !== '' ? $email : FROM),
    'X-Mailer: ann1678-contact',
];

if (!mb_send_mail(TO, $subject, implode("\n", $lines), implode("\r\n", $headers))) {
    fail('mail() failed');
}

back('?sent=1');
