from rsmesh_bbs.utils import bundle_mail_inbox_list, format_mail_inbox_summary_lines


class TestMailInboxMeshBundles:
    def test_summary_line_format(self):
        lines = format_mail_inbox_summary_lines(20, "RSN3", "Test Message to RSN1", "2026-09-17 07:06", "N")
        assert lines == [
            "20 2026-09-17 07:06 from RSN3 *",
            "     Subj: Test Message to RSN1",
        ]

    def test_bundle_groups_three_entries_per_message(self):
        rows = [
            (i, f"S{i}", f"Subject {i}", f"2026-09-17 07:{i:02d}", f"uid-{i}", "Y")
            for i in range(1, 8)
        ]
        bundles = bundle_mail_inbox_list(rows, footer="Select:", summaries_per_message=3)
        assert len(bundles) == 3
        assert bundles[0].count("Subj:") == 3
        assert bundles[1].count("Subj:") == 3
        assert bundles[2].count("Subj:") == 1
        assert bundles[-1].endswith("Select:")
