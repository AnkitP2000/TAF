from collections_helper.collections_spec_constants import MetaCrudParams

spec = {
    # Scope/Collection ops params
    MetaCrudParams.COLLECTIONS_TO_FLUSH: 0,
    MetaCrudParams.COLLECTIONS_TO_DROP: 200,

    MetaCrudParams.SCOPES_TO_DROP: 0,
    MetaCrudParams.SCOPES_TO_ADD_PER_BUCKET: 0,
    MetaCrudParams.COLLECTIONS_TO_ADD_FOR_NEW_SCOPES: 0,

    MetaCrudParams.COLLECTIONS_TO_ADD_PER_BUCKET: 0,

    MetaCrudParams.COLLECTIONS_TO_RECREATE: 200,

    MetaCrudParams.BUCKET_CONSIDERED_FOR_OPS: "all",
    MetaCrudParams.SCOPES_CONSIDERED_FOR_OPS: "all",
    MetaCrudParams.COLLECTIONS_CONSIDERED_FOR_OPS: "all",

    # Doc loading params
    "doc_crud": {

        MetaCrudParams.DocCrud.NUM_ITEMS_FOR_NEW_COLLECTIONS: 100000,

        MetaCrudParams.DocCrud.COMMON_DOC_KEY: "test_collections",
        MetaCrudParams.DocCrud.CREATE_PERCENTAGE_PER_COLLECTION: 22,
        MetaCrudParams.DocCrud.READ_PERCENTAGE_PER_COLLECTION: 20,
        MetaCrudParams.DocCrud.UPDATE_PERCENTAGE_PER_COLLECTION: 20,
        MetaCrudParams.DocCrud.REPLACE_PERCENTAGE_PER_COLLECTION: 0,
        MetaCrudParams.DocCrud.DELETE_PERCENTAGE_PER_COLLECTION: 20,
    },

    "subdoc_crud": {
        MetaCrudParams.SubDocCrud.XATTR_TEST: False,

        MetaCrudParams.SubDocCrud.INSERT_PER_COLLECTION: 0,
        MetaCrudParams.SubDocCrud.UPSERT_PER_COLLECTION: 0,
        MetaCrudParams.SubDocCrud.REMOVE_PER_COLLECTION: 0,
        MetaCrudParams.SubDocCrud.LOOKUP_PER_COLLECTION: 0,
    },

    MetaCrudParams.COLLECTIONS_CONSIDERED_FOR_CRUD: "all",
    MetaCrudParams.SCOPES_CONSIDERED_FOR_CRUD: "all",
    MetaCrudParams.BUCKETS_CONSIDERED_FOR_CRUD: "all"
}