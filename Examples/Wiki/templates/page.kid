<html xmlns:py="http://purl.org/kid/ns#">

<head>
  <title>Railways - Wiki example</title>
  <script type="text/javascript" src="/lib/prototype/prototype.js"></script>
  <script type="text/javascript" src="/lib/prototype/eip.js"></script>
  <link rel="stylesheet" media="screen" type="text/css" href="/lib/screen.css" />
</head>
<body>
  <div id="header">
  <h1>${title}</h1>
  </div>
  <div id="page" class='editable'></div>
  <div id="footer">
  <div align='right'>
    <a target='blank' href='/pages/${title}/source'>source</a> | <a target="_blank" href='/pages/${title}/render'>render</a>
  </div>
  <p><b>HELP</b><br />  To edit this page, simply move your cursor and click on the highligted text.
  This will allow you to <b>edit fragments</b> of the document. If you wish to
  <b>edit</b> the document <b>as a whole</b> simply click on the background between
  editable fragments.</p>
  </div>
</body>

<script type="text/javascript">
//<![CDATA[

// This returns source markup for the given HTML node. The HTML node was
// annotated by the Kiwi markup engine so that we know its start and end offset
// in the source text. In this respect, it is easy to request the original
// "fragment" we want to edit
function get_source(id) {
  var start = $(id).getAttribute('start')
  var end   = $(id).getAttribute('end')
  var req =  new Ajax.Request("/pages/${title}/source/" + start + "-" + end, { method:"GET", asynchronous:false })
  return req.transport.responseText
}

// This is the 'main' function that walks throught the `#page` element children
// and make editables those which are editable (this depends on the output given
// by the Kiwi markup engine, as editable elements have an `id` attribute
// starting with `KIWI` and suffixed by the element number.
function make_editable( node ) {
  // Skips non-element nodes
  if (node.nodeType != 1 ) return
  var id = node.id
  var edited = false
  // We look for editable nodes within the node
  if ( node.childNodes == undefined ) { return }
  for ( var i=0 ; i<node.childNodes.length ; i++ )
  { edited = make_editable(node.childNodes[i]) }
  // If there was no editable node, and that this node is editable, and not the
  // 'root' node (`KIWI1`), we make it editable.
  if ( id != undefined && id.indexOf("KIWI") == 0 )
  {
    Element.addClassName(node, 'kiwi-editable')
    EditInPlace.makeEditable({
      id:               id,
      // Indicates that we save the fragment using this URL
      save_url:         '/pages/${title}/' + node.getAttribute('start') + "-" + node.getAttribute('end'),
      type:             'textarea',
      editor_class:     'kiwi-editor',
      // The text to be edited is the source of this element
      set_editor_text:  get_source,
      // We may have nested editors, so we do not want a click to propagate to
      // parent editors
      stop_click_event: true,
      // Upon completion, we refresh the page
      on_save_complete: refresh_page,
      // When the editor is displayed, we ensure that its size is properly set
      on_editor_display: function (id, editor) {
        editor.setStyle({width: '100%'})
        editor.setStyle({height:Math.max(50,$(id).getDimensions().height)  + "px"})
      }
    })
    // Returning true means that this node is made editable
    return true
  }
  // false means that the node was not made editable
  return false
}

// Refereshes the page by removing all the `#page` children en replacing them by
// a freshly rendered new page. This could be done in a faster way by only
// replacing the node which has changed, but this would be a bit more
// complicated to implement.
function refresh_page( ) {
  var page = $('page')
  while ( page.childNodes.length > 0 ) { page.removeChild(page.childNodes[0]) }
  var req  = new Ajax.Request("/pages/${title}/render", { method:"GET", asynchronous:false })
  page.innerHTML = req.transport.responseText
  make_editable($('page'))
}

// We refresh the page at first, to load its content
refresh_page($('page'))
//]]>
</script>
</html>
<!-- vim: ts=2 sw=2 et syn=html 
-->
