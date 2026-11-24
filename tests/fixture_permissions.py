"""Mirror this build's exact requested hosts in disposable fixture extensions."""
import json, os, shutil, subprocess

def auth_permissions(extension):
    node=os.environ.get('PLAYWRIGHT_NODEJS_PATH') or shutil.which('node')
    uri=(extension/'lib/model.js').resolve().as_uri()
    code='const m=await import('+json.dumps(uri)+');console.log(JSON.stringify(m.AUTO_AUTH_PATTERNS));'
    return json.loads(subprocess.check_output([node,'--input-type=module','-e',code],text=True))
