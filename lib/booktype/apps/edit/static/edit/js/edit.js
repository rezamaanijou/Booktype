/*
  This file is part of Booktype.
  Copyright (c) 2013 Aleksandar Erkalovic <aleksandar.erkalovic@sourcefabric.org>
 
  Booktype is free software: you can redistribute it and/or modify
  it under the terms of the GNU Affero General Public License as published by
  the Free Software Foundation, either version 3 of the License, or
  (at your option) any later version.
 
  Booktype is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
  GNU Affero General Public License for more details.
 
  You should have received a copy of the GNU Affero General Public License
  along with Booktype.  If not, see <http://www.gnu.org/licenses/>.
*/

(function(win, jquery) {

	jquery.namespace('win.booktype.editor.edit');

  win.booktype.editor.edit = function() {
      var chapterID = null;
      var tabs = [];

      var saveContent = function(_call) {
          var content = Aloha.getEditableById('content').getContents();

          win.booktype.ui.notify('Saving chapter.');

          win.booktype.sendToCurrentBook({"command": "chapter_save",
                                  "chapterID": chapterID,
                                  "content": content,
                                  "continue": true,
                                  "comment": "",
                                  "author": "",
                                  "authorcomment": ""},
                                  function(data) {
                                    win.booktype.ui.notify();

                                    jquery('div.contentHeader span.info-message').html('Saved...');
                                    setTimeout(function() { jquery('div.contentHeader span.info-message').empty(); }, 2000);

                                    if(typeof _call !== 'undefined')
                                      _call();  
                                  });

       }

      var _show = function() {
        var t = win.booktype.ui.getTemplate('templateAlohaToolbar');

        jquery("DIV.contentHeader").html(t);
        jquery("DIV.contentHeader [rel=tooltip]").tooltip();


        Aloha.jQuery('#content').aloha().focus();      

        // HIDE
        jquery("#right-tabpane section[source_id=hold-tab]").hide();
        jquery('#hold-tab').hide();

        win.scrollTo(0, 0);
  //      jquery("#content").attr({ scrollTop: 0});

        jquery('#button-cancel').on('click', function() {
          // check if we are in the editor
          // if we are in the editor and is modified then message
          // save/not save and then call our callback
          if(Aloha.getEditableById('content').isModified()) {
              var result = confirm('Content has been modified. Do you want to save it before?');
              if(result) {
                  saveContent(function() {
                      win.booktype.editor.showTOC();
                  });
                  return;
              }
            }

          win.booktype.editor.showTOC();
        });

        jquery('#button-save').on('click', function() { saveContent(); });

        // Tabs

        var t1 = win.booktype.editor.createLeftTab('chapters-tab', 'big-icon-chapters');
        t1.isOnTop = true;
        t1.onActivate = function() {
            var $panel = jquery("SECTION[source_id=chapters-tab]");

            jquery('UL.edit-toc', $panel).empty();

            jquery.each(win.booktype.editor.data.chapters.chapters, function(i, chap) {
                if(chap.isSection) {
                  jquery('UL.edit-toc', $panel).append(jquery('<li><div><span class="section">'+chap.title+'</span></div></li>'));
                } else {
                  var $l = jquery('<a href="#"/>').text(chap.title);

                  $l.on('click', function() {
                      win.booktype.editor.editChapter(chap.chapterID);
                  });

                  var $a = jquery('<li/>').wrapInner('<div/>').wrapInner($l);
                  if(win.booktype.editor.getCurrentChapterID() == chap.chapterID)
                      ("LI", $a).addClass('active');
                
                  jquery('UL.edit-toc', $panel).append($a);                  
                }

            });
            return false;
        };

        var t2 = win.booktype.editor.createRightTab('attachments-tab', 'big-icon-attachment');
        t2.onActivate = function() {
            console.log('klikno na attachments');
        };

        var t3 = win.booktype.editor.createRightTab('notes-tab', 'big-icon-notes');
        t3.onActivate = function() {
            console.log('klikno na notes');
        };

        var t4 = win.booktype.editor.createRightTab('history-tab', 'big-icon-history');
        t4.onActivate = function() {
            console.log('klikno na history');
        };

        tabs = [t1, t2, t3, t4];
        win.booktype.editor.activateTabs(tabs);
      }

    var _hide = function() {

      Aloha.jQuery('#content').mahalo();      
      jquery('#content').empty();
      jquery("DIV.contentHeader").empty();

      win.booktype.editor.deactivateTabs(tabs);
      win.booktype.editor.hideAllTabs();
    }

    var _init = function() {
      Aloha.bind('beforepaste', function(e) {
        console.log('*before paste*');
      }); 

      Aloha.bind('paste', function(e) {
        console.log('*before paste*');
      }); 

      // check if content has changed
     //GENTICS.Aloha.Editable.activeEditable.isModified()
            Aloha.bind('aloha-smart-content-changed', function(a) {
              console.log('{}{}{}{}{}[ SMART CONTENT CHANGED {}{}{');
      })


      Aloha.bind('aloha-link-selected', function(a) {
          console.log('ODABRAO LINK NEKI');
          console.log(a);
      })

      Aloha.bind('aloha-image-selected', function(a) {
          console.log('ODABRAO IMAGE NEKI');
          console.log(a);
      })

     Aloha.bind('aloha-editable-activated', function() {
         console.log("TO JE TO SADA");
         console.log(Aloha.activeEditable);
      });



    }

    var setChapterID = function(id) {
      chapterID = id;
    }

    return {'init': _init,
            'name': 'edit',
            'show': _show,
            'setChapterID': setChapterID,
            'saveContent': saveContent,
            'hide': _hide};

  }();

  
})(window, jQuery);