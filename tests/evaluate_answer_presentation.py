from backend.rag.answer_polish import polish_grounded_answer


def main():
    original = """Based on the provided DBLP records, privacy is addressed in the context of federated learning through several works:

* A book covers privacy and incentives in federated learning (2020) [P1].
* A conference paper discusses differential privacy (2022) [P2].
"""

    polished = polish_grounded_answer(
        original,
        search_text="federated learning privacy",
    )

    print(polished)

    assert "Based on the provided DBLP" not in polished
    assert "Here are some relevant DBLP publications" in polished
    assert "- A book covers" in polished
    assert "[P1]" in polished
    assert "[P2]" in polished

    plain = (
        "Based on the provided DBLP evidence, "
        "the strongest matching record was published in 2022."
    )

    plain_polished = polish_grounded_answer(
        plain,
        search_text="example topic",
    )

    assert "provided DBLP" not in plain_polished
    assert "2022" in plain_polished

    print("\nPASS: grounded-answer presentation polish")


if __name__ == "__main__":
    main()
