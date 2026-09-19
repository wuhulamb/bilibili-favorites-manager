#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B站收藏夹管理工具 —— 基本增删改查（CRUD）
==========================================
收藏夹操作：
  folders                  查看全部收藏夹（R）
  folder-add <标题>         新建收藏夹（C）
  folder-rename <id> <新名> 收藏夹改名（U）
  folder-del <id>           删除收藏夹（D，会连带移除夹内收藏，慎用）

收藏内容操作：
  list <media_id>           查看收藏夹内容（R）
  fetch                     备份全部收藏夹内容快照到 data/（R）
  add <avid...> --to <夹id>  添加视频到收藏夹（C）
      [--from <夹id>]        提供后改为从该夹批量复制（copy）
  remove <avid...> --from <夹id>  从收藏夹移除视频（D）
  clean <media_id>          清空收藏夹内全部失效内容（D）

用法示例：
  bili.py folders
  bili.py list 1262420668
  bili.py add 678050583 927074448 --to 1262420668
  bili.py add 678050583 --from 3273814068 --to 1262420668
  bili.py remove 927074448 --from 1262420668
  bili.py clean 1262420668
  bili.py folder-add 新分类 && bili.py folder-rename <id> 新名字

通用参数（可放子命令前后）：
  --cookie PATH   cookie 文件（默认 ./cookie.txt，或用环境变量 BILI_COOKIE）
  --outdir DIR    data 目录（默认 ./data，仅 fetch 使用）
"""
import argparse, json, os, sys, time
import urllib.error, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
API = 'https://api.bilibili.com/x/v3/fav'

# ---------------------------------------------------------------- 会话与请求

def load_cookie(path):
    if not os.path.exists(path):
        sys.exit(f'[错误] 未找到 cookie 文件: {path}')
    items = {}
    for kv in open(path, encoding='utf-8').read().strip().split(';'):
        if '=' in kv:
            k, v = kv.strip().split('=', 1)
            items[k] = v
    return items

def get_csrf(c):
    v = c.get('bili_jct')
    if not v:
        sys.exit('[错误] cookie 中缺少 bili_jct (CSRF token)')
    return v

def get_uid(c):
    v = c.get('DedeUserID')
    if not v:
        sys.exit('[错误] cookie 中缺少 DedeUserID')
    return v

def req(cookies, method, path, params=None):
    """统一请求。返回解析后的 JSON（纯标准库 urllib 实现，无第三方依赖）。"""
    params = params or {}
    url = f'{API}/{path}'
    if method == 'GET':
        data = None
        if params:  # GET 参数拼接到查询串
            url += '?' + urllib.parse.urlencode(params)
    else:
        data = urllib.parse.urlencode(params).encode('utf-8')
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0',
        'Referer': 'https://space.bilibili.com/',
        'Cookie': '; '.join(f'{k}={v}' for k, v in cookies.items()),
    }
    if data:
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
    q = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(q, timeout=30) as r:
            raw = r.read().decode('utf-8')
    except urllib.error.HTTPError as e:
        raw = e.read().decode('utf-8', 'replace')  # HTTP 错误也读取返回体，继续走 JSON 解析
    except Exception:
        return {'code': 'PARSE_ERROR'}
    try:
        return json.loads(raw)
    except Exception:
        return {'code': 'PARSE_ERROR'}

def assert_ok(r, ctx, fatal=False):
    if r.get('code') != 0:
        msg = f'[失败] {ctx}: code={r.get("code")} message={r.get("message")} raw={str(r)[:160]}'
        (sys.exit if fatal else print)(msg)
        return False
    return True

def make_resources(avids):
    """avid 列表 -> 'avid:2,avid:2,...'（逗号分隔 + 类型后缀，必需！）"""
    return ','.join(f'{a}:2' for a in avids)

def chunks(seq, n=20):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]

# ---------------------------------------------------------------- 只读 API

def api_folders(cookies):
    r = req(cookies, 'GET', 'folder/created/list-all', {'up_mid': get_uid(cookies)})
    assert_ok(r, '获取收藏夹列表', fatal=True)
    return r['data'] or {}

def api_folder_medias(cookies, media_id, ps=20):
    """分页拉取收藏夹内容明细"""
    medias, pn = [], 1
    while True:
        r = req(cookies, 'GET', 'resource/list',
                {'media_id': media_id, 'platform': 'web', 'pn': pn, 'ps': ps})
        if r.get('code') != 0:
            break
        data = r.get('data') or {}
        medias.extend(data.get('medias') or [])
        if not data.get('has_more'):
            break
        pn += 1
    return medias

def find_title(folders, media_id):
    for f in folders.get('list') or []:
        if str(f['id']) == str(media_id):
            return f['title']
    return str(media_id)

# ---------------------------------------------------------------- 写操作

def op_copy(cookies, src, tar, avids):
    ok = True
    for b in chunks(avids):
        r = req(cookies, 'POST', 'resource/copy', {
            'src_media_id': src, 'tar_media_id': tar, 'mid': get_uid(cookies),
            'resources': make_resources(b), 'platform': 'web', 'csrf': get_csrf(cookies)})
        ok &= assert_ok(r, f'复制 {len(b)} 个到 {tar}')
    return ok

def op_deal(cookies, rid, tar):
    r = req(cookies, 'POST', 'resource/deal', {
        'rid': rid, 'type': '2', 'add_media_ids': tar,
        'platform': 'web', 'csrf': get_csrf(cookies)})
    return assert_ok(r, f'添加 {rid}')

def op_batch_del(cookies, media_id, avids):
    ok = True
    for b in chunks(avids):
        r = req(cookies, 'POST', 'resource/batch-del', {
            'resources': make_resources(b), 'media_id': media_id,
            'platform': 'web', 'csrf': get_csrf(cookies)})
        ok &= assert_ok(r, f'移除 {len(b)} 个')
    return ok

def op_folder_add(cookies, title, privacy=0):
    r = req(cookies, 'POST', 'folder/add', {'title': title, 'privacy': privacy, 'csrf': get_csrf(cookies)})
    assert_ok(r, f'新建收藏夹「{title}」', fatal=True)
    return r['data']['id']

def op_folder_edit(cookies, media_id, title, privacy=0):
    r = req(cookies, 'POST', 'folder/edit',
            {'media_id': media_id, 'title': title, 'privacy': privacy, 'csrf': get_csrf(cookies)})
    assert_ok(r, f'改名 {media_id} -> {title}', fatal=True)

def op_folder_del(cookies, media_ids):
    r = req(cookies, 'POST', 'folder/del',
            {'media_ids': ','.join(media_ids), 'csrf': get_csrf(cookies)})
    assert_ok(r, f'删除收藏夹 {",".join(media_ids)}', fatal=True)

def op_clean(cookies, media_id):
    r = req(cookies, 'POST', 'resource/clean', {'media_id': media_id, 'csrf': get_csrf(cookies)})
    assert_ok(r, f'清空失效 {media_id}', fatal=True)

# ---------------------------------------------------------------- 命令实现

def cmd_folders(cookies, args):
    data = api_folders(cookies)
    print(f'共 {data.get("count", len(data.get("list") or []))} 个收藏夹:')
    for f in data.get('list') or []:
        priv = '私有' if (f['attr'] & 1) else '公开'
        print(f'  id={f["id"]:<12} {f["title"]:<10} [{priv}] {f["media_count"]} 个')

def cmd_list(cookies, args):
    folders = api_folders(cookies)
    title = find_title(folders, args.media_id)
    medias = api_folder_medias(cookies, args.media_id)
    print(f'== {title} (id={args.media_id}) : {len(medias)} 个 ==')
    for m in medias:
        status = '已失效' if m.get('attr', 0) else '正常'
        dur = m.get('duration', 0)
        mm, ss = divmod(dur, 60)
        dstr = f'{mm // 60}:{mm % 60:02d}:{ss:02d}' if mm >= 60 else f'{mm}:{ss:02d}'
        up = (m.get('upper') or {}).get('name', '-')
        print(f'  [{status}] {m.get("title", "")[:50]:<50} BV:{m.get("bvid", "-"):<14} '
              f'UP:{up:<16} {dstr}')

def cmd_fetch(cookies, args):
    outdir = args.outdir
    os.makedirs(outdir, exist_ok=True)
    folders = api_folders(cookies)
    lst = folders.get('list') or []
    json.dump(lst, open(os.path.join(outdir, 'folders.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    for f in lst:
        mid = str(f['id'])
        medias = api_folder_medias(cookies, mid)
        json.dump({'media_id': mid, 'title': f['title'], 'medias': medias},
                  open(os.path.join(outdir, f'{mid}.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False)
        print(f'  {f["title"]}: {len(medias)}')
    print(f'快照完成 -> {outdir}')

def cmd_folder_add(cookies, args):
    nid = op_folder_add(cookies, args.title)
    print(f'已创建收藏夹「{args.title}」, id={nid}')

def cmd_folder_rename(cookies, args):
    op_folder_edit(cookies, args.media_id, args.title)
    print(f'已完成: {args.media_id} -> {args.title}')

def cmd_folder_del(cookies, args):
    folders = api_folders(cookies)
    print(f'删除 {args.media_id}（{find_title(folders, args.media_id)}）...')
    # 先清空内容，保证删除安全（默认收藏夹不可删，由接口拒绝）
    op_batch_del(cookies, args.media_id,
                 [m['id'] for m in api_folder_medias(cookies, args.media_id)])
    op_folder_del(cookies, [args.media_id])
    print('已删除')

def cmd_add(cookies, args):
    avids = args.avids
    if args.frm:  # 从源夹批量复制
        for b in chunks(avids):
            op_copy(cookies, args.frm, args.to, b)
    else:         # 逐条直接添加（不依赖源夹，可用于恢复）
        for a in avids:
            op_deal(cookies, a, args.to)
            time.sleep(0.3)
    print(f'已添加 {len(avids)} 个到 {args.to}')

def cmd_remove(cookies, args):
    op_batch_del(cookies, args.frm, args.avids)
    print(f'已从 {args.frm} 移除 {len(args.avids)} 个')

def cmd_clean(cookies, args):
    for mid in args.media_ids:
        op_clean(cookies, mid)
        print(f'已清空 {mid} 的失效内容')

# ---------------------------------------------------------------- 入口

def main():
    p = argparse.ArgumentParser(description='B站收藏夹 CRUD 工具')
    p.add_argument('--cookie', default=os.environ.get('BILI_COOKIE') or os.path.join(HERE, 'cookie.txt'))
    p.add_argument('--outdir', default=os.path.join(HERE, 'data'))
    sub = p.add_subparsers(dest='cmd', required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument('--cookie', default=os.environ.get('BILI_COOKIE') or os.path.join(HERE, 'cookie.txt'))
    common.add_argument('--outdir', default=os.path.join(HERE, 'data'))

    sp = sub.add_parser('folders', parents=[common]); sp.set_defaults(func=cmd_folders)
    sp = sub.add_parser('list', parents=[common]); sp.add_argument('media_id'); sp.set_defaults(func=cmd_list)
    sp = sub.add_parser('fetch', parents=[common]); sp.set_defaults(func=cmd_fetch)
    sp = sub.add_parser('folder-add', parents=[common]); sp.add_argument('title'); sp.set_defaults(func=cmd_folder_add)
    sp = sub.add_parser('folder-rename', parents=[common]); sp.add_argument('media_id'); sp.add_argument('title'); sp.set_defaults(func=cmd_folder_rename)
    sp = sub.add_parser('folder-del', parents=[common]); sp.add_argument('media_id'); sp.set_defaults(func=cmd_folder_del)
    sp = sub.add_parser('add', parents=[common])
    sp.add_argument('avids', nargs='+')
    sp.add_argument('--to', dest='to', required=True)
    sp.add_argument('--from', dest='frm', default=None)
    sp.set_defaults(func=cmd_add)
    sp = sub.add_parser('remove', parents=[common])
    sp.add_argument('avids', nargs='+')
    sp.add_argument('--from', dest='frm', required=True)
    sp.set_defaults(func=cmd_remove)
    sp = sub.add_parser('clean', parents=[common]); sp.add_argument('media_ids', nargs='+'); sp.set_defaults(func=cmd_clean)

    args = p.parse_args()
    # 所有命令都需要 cookie，统一在此加载并校验 CSRF / 用户 ID
    cookies = None
    if args.cmd in ('folders', 'list', 'fetch', 'folder-add', 'folder-rename', 'folder-del', 'add', 'remove', 'clean'):
        cookies = load_cookie(args.cookie)
        get_csrf(cookies); get_uid(cookies)
    args.func(cookies, args)

if __name__ == '__main__':
    main()