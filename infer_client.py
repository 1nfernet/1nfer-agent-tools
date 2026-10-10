#!/usr/bin/env python3
"""Manual 1NFER key-only signup, invoices and bounded paid requests. No wallet keys."""
import argparse,json,os,re,secrets,ssl,stat,sys,time
from decimal import Decimal,InvalidOperation
from pathlib import Path
from urllib.error import HTTPError,URLError
from urllib.request import Request,build_opener,ProxyHandler,HTTPSHandler,HTTPRedirectHandler
ORIGIN='https://1nfer.net'
KEY=re.compile(r'hs-live-[A-Za-z0-9_-]{16,256}')
ACCOUNT=re.compile(r'key_[ABCDEFGHJKLMNPQRSTUVWXYZ23456789]{8,32}')
class Error(Exception):pass
class NoRedirect(HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):raise Error('Redirect refused.')
def private_write(path,data):
 fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
 with os.fdopen(fd,'w') as f:json.dump(data,f);f.flush();os.fsync(f.fileno())
def private_read(path):
 fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
 with os.fdopen(fd) as f:
  info=os.fstat(f.fileno())
  if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or stat.S_IMODE(info.st_mode)&0o077:raise Error('Private file must belong to you and have no group/other access. Use chmod 600.')
  data=f.read(8193)
  if len(data)>8192:raise Error('Private file is too large.')
  return json.loads(data)
def key_read(path):
 key=private_read(path).get('api_key')
 if not isinstance(key,str) or not KEY.fullmatch(key):raise Error('Invalid saved API key.')
 return key
def amount(raw):
 try:
  n=Decimal(raw)
  if not n.is_finite() or n<1 or n>2000 or n.as_tuple().exponent < -2:raise Error('Use $1–2000 with at most two decimals; check runtime limits.')
  return format(n,'.2f')
 except (InvalidOperation,TypeError):raise Error('Invalid credit amount.') from None
def payment_plan(invoice,asset,max_usd,now=None):
 now=int(time.time()) if now is None else now
 if invoice.get('status')!='pending' or not isinstance(invoice.get('expires_at'),int) or isinstance(invoice['expires_at'],bool) or invoice['expires_at']<=now:raise Error('Invoice is not pending and unexpired. Do not pay; read its current status.')
 cap=Decimal(amount(max_usd));total=Decimal(str(invoice.get('total_usd','NaN')))
 if not total.is_finite() or total<=0 or total>cap:raise Error('Invoice exceeds the authorized USD budget.')
 networks={'XMR':'monero-mainnet','BTC':'bitcoin-mainnet','LTC':'litecoin-mainnet','ETH':'ethereum-mainnet','TRX':'tron-mainnet','USDT':'tron-mainnet'}
 rows=[r for r in invoice.get('addresses',[]) if r.get('asset')==asset]
 if len(rows)!=1:raise Error('No unique verified instruction for this asset; inspect native invoice and sender binding.')
 row=rows[0];value=Decimal(str(row.get('amount','NaN')))
 if row.get('network')!=networks.get(asset) or not value.is_finite() or value<=0 or not isinstance(row.get('address'),str) or not 8<=len(row['address'])<=128:raise Error('Payment instruction is invalid.')
 if row.get('requires_sender_binding') is True and row.get('sender_bound') is not True:raise Error('Bind the actual sender on the native invoice before paying.')
 if not re.fullmatch(r'inv_[A-Za-z0-9_-]{32}',str(invoice.get('invoice_id',''))):raise Error('Invalid invoice identity.')
 return {'invoice_id':invoice['invoice_id'],'account_id':invoice['account_id'],'asset':asset,'network':row['network'],'address':row['address'],'amount':format(value,'f'),'invoice_total_usd':format(total,'.2f'),'expires_at':invoice['expires_at'],'network_fee_included':False,'transfer_executed':False,'next_action':'Use your own authorized wallet tool with a separate network fee cap; recheck invoice just before sending. Wait for credited and check account.'}
class Client:
 def __init__(self,key=None,opener=None):
  self.key=key;self.opener=opener or build_opener(ProxyHandler({}),NoRedirect(),HTTPSHandler(context=ssl.create_default_context()))
 def request(self,path,body=None,private=False):
  if not re.fullmatch(r'/v1/(registration|payments/terms|models|account|account/referrals/funnel|agents/register|account/topups|chat/completions|invoices/inv_[A-Za-z0-9_-]{32})',path):raise Error('Unsupported fixed-origin route.')
  headers={'Accept':'application/json'}
  if private:
   if not self.key or not KEY.fullmatch(self.key):raise Error('Saved API key is required.')
   headers['Authorization']='Bearer '+self.key
  data=json.dumps(body,ensure_ascii=False).encode() if body is not None else None
  if data is not None:headers['Content-Type']='application/json'
  try:
   with self.opener.open(Request(ORIGIN+path,data=data,headers=headers,method='POST' if body is not None else 'GET'),timeout=210 if path=='/v1/chat/completions' else 45) as r:
    raw=r.read(262145)
    if len(raw)>262144:raise Error('Response exceeds the bounded size.')
    value=json.loads(raw)
    if not isinstance(value,dict):raise Error('Invalid API response.')
    return value
  except HTTPError as e:raise Error('API HTTP '+str(e.code)+'; no automatic retry.') from None
  except (URLError,TimeoutError):raise Error('Request outcome uncertain. No automatic retry; keep your saved key and invoice intent.') from None
 def register(self,referral_code=None):
  if self.request('/v1/registration').get('enabled') is not True:raise Error('Registration is closed.')
  if referral_code is not None and (not isinstance(referral_code,str) or not ACCOUNT.fullmatch(referral_code)):raise Error('Invalid public referral code.')
  return self.request('/v1/agents/register',{'api_key':self.key,**({'referral_code':referral_code} if referral_code else {})})
 def topup(self,credit,intent_file,asset):
  credit=amount(credit);terms=self.request('/v1/payments/terms')
  if terms.get('enabled') is not True:raise Error('New invoices are closed.')
  if not isinstance(asset,str) or asset not in {'XMR','BTC','LTC','ETH','TRX','USDT'} or not any(r.get('asset')==asset for r in terms.get('supported_assets',[]) if isinstance(r,dict)):raise Error('Choose an enabled --asset from the current payment terms.')
  if not Decimal(terms['min_credit_usd'])<=Decimal(credit)<=Decimal(terms['max_credit_usd']):raise Error('Amount is outside runtime limits.')
  account=self.request('/v1/account',private=True)
  path=Path(intent_file)
  if path.exists():
   intent=private_read(path)
   if intent.get('account_id')!=account['account_id'] or intent.get('credit_usd')!=credit or intent.get('asset')!=asset:raise Error('Saved invoice intent belongs to another amount, currency or account. Keep the original intent; reconcile older invoices before creating a new one.')
  else:
   intent={'account_id':account['account_id'],'credit_usd':credit,'asset':asset,'idempotency_key':secrets.token_urlsafe(24)};private_write(path,intent)
  if not re.fullmatch(r'[A-Za-z0-9_-]{16,128}',intent.get('idempotency_key','')):raise Error('Invalid saved invoice intent.')
  value=self.request('/v1/account/topups',{k:intent[k] for k in ('credit_usd','asset','idempotency_key')},private=True)
  if value.get('selected_asset')!=asset or value.get('account_id')!=account['account_id']:raise Error('Invoice currency or account is not confirmed. Do not pay; reconcile using the saved intent.')
  return value
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['init','register','account','models','terms','invoice','payment-plan','referrals','topup','chat']);p.add_argument('--key-file');p.add_argument('--referral-code');p.add_argument('--asset',choices=['XMR','BTC','LTC','ETH','TRX','USDT']);p.add_argument('--max-usd');p.add_argument('--intent-file');p.add_argument('--usd');p.add_argument('--invoice');p.add_argument('--model');p.add_argument('--prompt-file');p.add_argument('--max-tokens',type=int,default=32);p.add_argument('--confirm-paid',action='store_true');a=p.parse_args()
 try:
  if a.action=='init':
   if not a.key_file:raise Error('--key-file is required.')
   if a.referral_code and not ACCOUNT.fullmatch(a.referral_code):raise Error('Invalid public referral code.')
   private_write(a.key_file,{'api_key':'hs-live-'+secrets.token_hex(32),**({'referral_code':a.referral_code} if a.referral_code else {})});print('Key saved privately. No registration or purchase made.');return
  if a.referral_code:raise Error('Set referral code only during init; the saved registration intent is reused.')
  key=key_read(a.key_file) if a.key_file else None;c=Client(key)
  if a.action in ('register','account','referrals','topup','chat') and not key:raise Error('--key-file is required.')
  if a.action=='register':v=c.register(private_read(a.key_file).get('referral_code'))
  elif a.action=='referrals':
   account=c.request('/v1/account',private=True);code=account.get('account_id')
   if not isinstance(code,str) or not ACCOUNT.fullmatch(code):raise Error('Invalid public account identifier.')
   v={'invitation_url':ORIGIN+'/r/'+code,'reward_terms_source':ORIGIN+'/guides/crypto-inference-agents.html#referral-pilot','funnel':c.request('/v1/account/referrals/funnel',private=True)}
  elif a.action=='account':v=c.request('/v1/account',private=True)
  elif a.action=='models':v=c.request('/v1/models',private=bool(key))
  elif a.action=='terms':v=c.request('/v1/payments/terms')
  elif a.action in ('invoice','payment-plan'):
   if not a.invoice or not re.fullmatch(r'inv_[A-Za-z0-9_-]{32}',a.invoice):raise Error('Valid --invoice is required.')
   v=c.request('/v1/invoices/'+a.invoice)
   if a.action=='payment-plan':
    if not a.asset or not a.max_usd:raise Error('--asset and --max-usd are required.')
    v=payment_plan(v,a.asset,a.max_usd)
  elif a.action=='topup':
   if not a.intent_file or not a.usd or not a.asset:raise Error('--intent-file, --usd and --asset are required.')
   v=c.topup(a.usd,a.intent_file,a.asset)
  elif a.action=='chat':
   if not a.confirm_paid or not a.model or not a.prompt_file:raise Error('Paid chat requires --confirm-paid, --model and --prompt-file.')
   if not 1<=a.max_tokens<=128:raise Error('Use 1–128 output tokens for this small test client.')
   with open(a.prompt_file,'rb') as f:raw=f.read(16000001)
   if not raw or len(raw)>16000000:raise Error('Use a nonempty prompt up to 16,000,000 UTF-8 bytes; provider token limits and sufficient credit still apply.')
   prompt=raw.decode('utf-8')
   if KEY.search(prompt):raise Error('Do not put API secrets in prompts.')
   models=c.request('/v1/models',private=True).get('data',[])
   if not any(m.get('id')==a.model for m in models):raise Error('Model is not in your live catalogue.')
   if Decimal(str(c.request('/v1/account',private=True).get('balance_usd',0)))<=0:raise Error('Confirmed API credit is required.')
   v=c.request('/v1/chat/completions',{'model':a.model,'messages':[{'role':'user','content':prompt}],'max_tokens':a.max_tokens,'stream':False},private=True)
   if v.get('model')!=a.model:raise Error('Unexpected returned model; request is not repeated.')
  print(KEY.sub('[private key]',json.dumps(v,ensure_ascii=False)))
 except (Error,OSError,ValueError,KeyError,InvalidOperation) as e:
  # Never include arbitrary paths, input data, remote response bodies or bearer values.
  print(str(e) if isinstance(e,Error) else 'Local file or response validation failed; no automatic retry.',file=sys.stderr);return 1
if __name__=='__main__':sys.exit(main())
