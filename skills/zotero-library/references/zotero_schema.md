# Zotero Local Schema Notes

This reference documents the local Zotero tables used by `zotero_read.py`. Use it only when debugging or extending queries.

## Core Tables

- `collections(collectionID, collectionName, parentCollectionID, libraryID, key)`
- `collectionItems(collectionID, itemID, orderIndex)`
- `items(itemID, itemTypeID, dateAdded, dateModified, libraryID, key, version, synced)`
- `itemTypes(itemTypeID, typeName)`
- `fields(fieldID, fieldName)`
- `itemData(itemID, fieldID, valueID)`
- `itemDataValues(valueID, value)`
- `creators(creatorID, firstName, lastName, fieldMode)`
- `itemCreators(itemID, creatorID, creatorTypeID, orderIndex)`
- `creatorTypes(creatorTypeID, creatorType)`
- `tags(tagID, name)`
- `itemTags(itemID, tagID, type)`
- `itemAttachments(itemID, parentItemID, linkMode, contentType, path)`
- `itemNotes(itemID, parentItemID, note, title)`

## Important Item Types

Observed in the target library:

- `attachment`: item type ID 3
- `note`: item type ID 28
- ordinary bibliographic records vary, for example `journalArticle` and `book`

Always query by `itemTypes.typeName`, not hard-coded IDs.

## Attachment Paths

For stored files, `itemAttachments.path` often uses Zotero's `storage:<filename>` format. Resolve it as:

```text
<ZOTERO_DATA_DIR>/storage/<attachment item key>/<filename>
```

The attachment item key comes from `items.key` for the attachment item itself.

Full-text cache is usually:

```text
<ZOTERO_DATA_DIR>/storage/<attachment item key>/.zotero-ft-cache
```

## Notes

Standalone notes have `itemNotes.parentItemID` set to `NULL`. Child notes have `parentItemID` pointing at the parent bibliographic item's `itemID`.

Do not create notes locally by inserting rows. Use the Zotero Web API for writes.
