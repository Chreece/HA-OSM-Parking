"""One-time source preparation; removed by the initial preview-build commit."""
from pathlib import Path
root=Path(__file__).resolve().parent
locale=root/'locales.py'
text=locale.read_text(encoding='utf-8').replace("\ntr':", "\n'tr':")
compile(text,str(locale),'exec')
locale.write_text(text,encoding='utf-8')
source=root/'explorer.js'
text=source.read_text(encoding='utf-8')
replacements={
"value === null || value === undefined || typeof value === 'boolean'":"value === null || value === undefined || typeof value === 'boolean' || typeof value === 'object'",
"hass?.language,hass?.themes?.darkMode,this._themeChoice]":"hass?.language,hass?.themes?.darkMode,this._themeChoice,hass?.user?.id]",
"if(this.config.remember_filters) {":"if(this.config.remember_filters && this.config.show_filters!==false) {",
"if(document.activeElement!==e.search) e.search.value=this._ui.query;":"if(e.search.value!==this._ui.query) e.search.value=this._ui.query;",
"({'no':0,'yes':1}[x.fee] ?? 2)-({'no':0,'yes':1}[y.fee] ?? 2)":"(x.fee==='no'?0:x.fee==='yes'?1:2)-(y.fee==='no'?0:y.fee==='yes'?1:2)",
"(item.data_sources || []).join(', ')":"(Array.isArray(item.data_sources)?item.data_sources:[]).join(', ')",
".toLocaleLowerCase()":".toLocaleLowerCase().normalize('NFD').replace(/\\p{M}/gu,'')",
}
for old,new in replacements.items():
    if old in text:text=text.replace(old,new)
    else:assert new in text,old
source.write_text(text,encoding='utf-8')
print('EXPLORER_SOURCE_PREPARED')
