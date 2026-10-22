from app.core.ids import PUBLIC_ID_ALPHABET, PUBLIC_ID_LENGTH, new_public_id, tree_code


def test_public_id_shape():
    for _ in range(500):
        pid = new_public_id()
        assert len(pid) == PUBLIC_ID_LENGTH
        assert set(pid) <= set(PUBLIC_ID_ALPHABET)


def test_public_id_has_no_ambiguous_chars():
    assert not set("0o1li") & set(PUBLIC_ID_ALPHABET)


def test_public_ids_are_not_sequential_or_repeated():
    ids = [new_public_id() for _ in range(2000)]
    assert len(set(ids)) == len(ids)
    assert ids != sorted(ids)


def test_tree_code_format():
    assert tree_code(1) == "ARV-001"
    assert tree_code(15) == "ARV-015"
