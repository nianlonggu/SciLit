export async function searchDocumentsRequest(
    context,
    keywords,
    nResults,
    nlp_server_address,
    timeout = 10000
) {
    const data = {
        ranking_variable: context,
        keywords: keywords.replaceAll(";", "\\t"),
        paper_list: "",
        prefetch_nResults_per_collection: 100,
        nResults: nResults,
        requires_removing_duplicates: true,
        requires_additional_prefetching: false,
        requires_reranking: true,
        reranking_method: "scibert",
    };
    const controller = new AbortController();
    const timeout_id = setTimeout(() => controller.abort(), timeout);
    const requestOptions = {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
        signal: controller.signal,
    };
    const response = await fetch(
        nlp_server_address + "/ml-api/doc-search/v1.0",
        requestOptions
    );
    const response_data = await response.json();
    const response_data_response = response_data["response"];
    clearTimeout(timeout_id);

    return response_data_response;
}

export async function get_papers_content(
    paper_list,
    nlp_server_address,
    timeout = 5000
) {
    const data = {
        paper_list: paper_list,
        projection: null,
    };
    const controller = new AbortController();
    const timeout_id = setTimeout(() => controller.abort(), timeout);
    const requestOptions = {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
        signal: controller.signal,
    };
    const response = await fetch(
        nlp_server_address + "/ml-api/get-papers/v1.0",
        requestOptions
    );
    const response_data = await response.json();
    const response_data_response = await response_data["response"];
    clearTimeout(timeout_id);

    return response_data_response;
}

function get_sentence_list_from_section(section) {
    const para_sentence_list = section["section_text"].map(
        (para_item, para_idx) => {
            return para_item["paragraph_text"].map((sen_item, sen_idx) => {
                return sen_item["sentence_text"];
            });
        }
    );

    let sen_list = [];
    for (let i = 0; i < para_sentence_list.length; i++) {
        sen_list = sen_list.concat(para_sentence_list[i]);
    }
    return sen_list;
}

function get_sentence_list_from_paper_content(paper_content) {
    const Abstract_Parsed = (paper_content.Content ?? {}).Abstract_Parsed ?? [];
    const Fullbody_Parsed = (paper_content.Content ?? {}).Fullbody_Parsed ?? [];
    const section_list =
        Fullbody_Parsed.length > 0 ? Fullbody_Parsed : Abstract_Parsed;
    let sentence_list = [];
    for (let sec_i = 0; sec_i < section_list.length; sec_i++) {
        sentence_list = sentence_list.concat(
            get_sentence_list_from_section(section_list[sec_i])
        );
    }

    return sentence_list;
}

export async function extract_highlights_from_papers(
    paper_content_list,
    nlp_server_address,
    timeout = 5000
) {
    const batch_sentence_list = paper_content_list.map((item, idx) => {
        return get_sentence_list_from_paper_content(item);
    });
    const batch_output = await Promise.all(
        batch_sentence_list.map(async (item, idx) => {
            const data = { sentence_list: item };
            const controller = new AbortController();
            const timeout_id = setTimeout(() => controller.abort(), timeout);
            const requestOptions = {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(data),
                signal: controller.signal,
            };
            const response = await fetch(
                nlp_server_address + "/ml-api/extractive-summarize/v1.0",
                requestOptions
            );
            const response_data = await response.json();
            const response_data_response = await response_data["response"];
            const response_data_summary = await response_data_response[
                "summary"
            ];
            clearTimeout(timeout_id);
            return response_data_summary;
        })
    );

    return batch_output;
}

export async function generate_citations_for_papers(
    paper_content_list,
    context,
    keywords,
    nlp_server_address,
    timeout = 5000
) {
    const context_list = paper_content_list.map((item, idx) => {
        return context;
    });
    const keywords_list = paper_content_list.map((item, idx) => {
        return keywords.replaceAll(";", "\\t");
    });
    const papers = paper_content_list.map((item, idx) => {
        return {
            Title: item.Title ?? "",
            Abstract: item.Abstract ?? "",
        };
    });
    const data = {
        context_list: context_list,
        keywords_list: keywords_list,
        papers: papers,
    };
    const controller = new AbortController();
    const timeout_id = setTimeout(() => controller.abort(), timeout);
    const requestOptions = {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
        signal: controller.signal,
    };
    const response = await fetch(
        nlp_server_address + "/ml-api/generate-citation/v1.0",
        requestOptions
    );
    const response_data = await response.json();
    const response_data_response = await response_data["response"];
    clearTimeout(timeout_id);
    const gen_text_list = response_data_response.map((item, idx) => {
        return item.trim();
    });

    return gen_text_list;
}

export async function callback_paginating_papers(
    paper_id_list,
    context,
    keywords,
    set_log_search_progress,
    nlp_server_address
) {
    try {
        const paper_content_list = await get_papers_content(
            paper_id_list,
            nlp_server_address
        );
        set_log_search_progress("extracting highlights ...");
        const extracted_highlights_list = await extract_highlights_from_papers(
            paper_content_list,
            nlp_server_address
        );
        const spans_for_extracted_highlights_list = await Promise.all(
            extracted_highlights_list.map(async (extracted_sens, _) => {
                const spans_per_paper = await Promise.all(
                    extracted_sens.map(async (sen, _) => {
                        const spans_per_sen = await text_processing(
                            {
                                data: {
                                    text: "• " + sen,
                                    // text:sen,
                                    keywords: keywords,
                                },
                                mode: "highlight_text_given_keywords",
                            },
                            nlp_server_address
                        );

                        return spans_per_sen;
                    })
                );
                return spans_per_paper;
            })
        );
        const extracted_highlights_info_list = [];
        for (
            let paper_idx = 0;
            paper_idx < extracted_highlights_list.length;
            paper_idx++
        ) {
            const extracted_highlights_info_per_paper = [];
            for (
                let sen_idx = 0;
                sen_idx < extracted_highlights_list[paper_idx].length;
                sen_idx++
            ) {
                extracted_highlights_info_per_paper.push({
                    text: "• " + extracted_highlights_list[paper_idx][sen_idx],
                    // text: extracted_highlights_list[paper_idx][sen_idx],
                    highlight_spans:
                        spans_for_extracted_highlights_list[paper_idx][sen_idx],
                });
            }
            extracted_highlights_info_list.push(
                extracted_highlights_info_per_paper
            );
        }

        set_log_search_progress("generating citations ...");

        const gen_text_list = await generate_citations_for_papers(
            paper_content_list,
            context,
            keywords,
            nlp_server_address
        );
        const gen_text_info_list = await Promise.all(
            gen_text_list.map(async (gen_sen, _) => {
                const spans_gen_sen = await text_processing(
                    {
                        data: {
                            text: gen_sen,
                            keywords: keywords,
                        },
                        mode: "highlight_text_given_keywords",
                    },
                    nlp_server_address
                );
                return {
                    text: gen_sen,
                    highlight_spans: spans_gen_sen,
                };
            })
        );

        let unhighlighted_paper_info_list = [];
        for (let i = 0; i < paper_id_list.length; i++) {
            unhighlighted_paper_info_list.push({
                id_info: paper_id_list[i],
                is_showing_fulltext: false,
                content_info: paper_content_list[i],
                highlights_info: extracted_highlights_info_list[i],
                generated_citation_info: gen_text_info_list[i],
            });
        }

        set_log_search_progress("rendering ...");

        const paper_info_list = await Promise.all(
            unhighlighted_paper_info_list.map(async (item, idx) => {
                return await highlight_paper(item, nlp_server_address);
            })
        );
        set_log_search_progress("");
        return paper_info_list;
    } catch {
        set_log_search_progress(
            "Error: please refresh the page and try again."
        );
        return null;
    }
}

export async function callback_search_pipeline(
    input_context_ref,
    input_keywords_ref,
    input_gen_cit_ref,

    set_selected_cited_paper_info,
    set_paper_offset,
    setPaperInfoList,
    set_log_search_progress,

    nResults,
    num_papers_per_page,
    nlp_server_address
) {
    const context = input_context_ref.current.value;
    const keywords = input_keywords_ref.current.value;
    input_gen_cit_ref.current.value = "";
    set_selected_cited_paper_info(null);
    const new_paper_offset = 0;

    if (context === "" && keywords === "") {
        set_paper_offset(new_paper_offset);
        setPaperInfoList([]);
    } else {
        try {
            set_log_search_progress("searching for documents ...");
            const paper_id_list = await searchDocumentsRequest(
                context,
                keywords,
                nResults,
                nlp_server_address
            );

            const paper_info_list_slice = await callback_paginating_papers(
                paper_id_list.slice(
                    new_paper_offset,
                    new_paper_offset + num_papers_per_page
                ),
                context,
                keywords,
                set_log_search_progress,
                nlp_server_address
            );

            const paper_info_list = paper_id_list.map((item, idx) => {
                if (
                    idx >= new_paper_offset &&
                    idx < new_paper_offset + num_papers_per_page &&
                    idx - new_paper_offset < paper_info_list_slice.length
                ) {
                    return paper_info_list_slice[idx - new_paper_offset];
                } else {
                    return {
                        id_info: item,
                        is_showing_fulltext: false,
                    };
                }
            });
            set_paper_offset(new_paper_offset);
            setPaperInfoList(paper_info_list);
        } catch {
            set_log_search_progress(
                "Timeout: please refresh the page and try again."
            );
            set_paper_offset(0);
            setPaperInfoList([]);
        }
    }
}

export async function title_generic_search(
    titles,
    nlp_server_address,
    timeout = 5000
) {
    const query_data = {
        titles: titles,
        projection: {},
    };
    const controller = new AbortController();
    const timeout_id = setTimeout(() => controller.abort(), timeout);
    const requestOptions = {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(query_data),
        signal: controller.signal,
    };
    const response = await fetch(
        nlp_server_address + "/ml-api/title-generic-search/v1.0",
        requestOptions
    );
    const response_data = await response.json();
    const response_data_response = response_data["response"];
    clearTimeout(timeout_id);

    return response_data_response;
}

export async function text_processing(
    data,
    nlp_server_address,
    timeout = 5000
) {
    const controller = new AbortController();
    const timeout_id = setTimeout(() => controller.abort(), timeout);
    const requestOptions = {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
        signal: controller.signal,
    };
    const response = await fetch(
        nlp_server_address + "/ml-api/process/v1.0",
        requestOptions
    );
    const response_data = await response.json();
    const response_data_response = await response_data["response"];
    clearTimeout(timeout_id);

    return response_data_response;
}

export async function highlight_paper(paper_to_highlight, nlp_server_address) {
    let paper_info = JSON.parse(JSON.stringify(paper_to_highlight));
    const highlighted_paper_and_ref_sen_info = await text_processing(
        {
            data: {
                paper: paper_info.content_info,
                ref_sentences: paper_info.highlights_info.map((item, idx) => {
                    return item.text;
                }),
            },
            mode: "highlight_paper_given_ref_sentences",
        },
        nlp_server_address
    );
    const highlighted_paper =
        highlighted_paper_and_ref_sen_info.highlighted_paper;
    const ref_sentences_with_matched_sen_ids =
        highlighted_paper_and_ref_sen_info.ref_sentences_with_matched_sen_ids;

    for (let i = 0; i < ref_sentences_with_matched_sen_ids.length; i++) {
        paper_info.highlights_info[i]["matched_sen_id_info"] =
            ref_sentences_with_matched_sen_ids[i]["matched_sen_id_info"];
    }
    paper_info.content_info = highlighted_paper;
    return paper_info;
}

export async function export_citation(
    paper_id_info,
    nlp_server_address,
    timeout = 10000
) {
    const data = {
        paper_list: [paper_id_info],
    };

    const controller = new AbortController();
    const timeout_id = setTimeout(() => controller.abort(), timeout);
    const requestOptions = {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
        signal: controller.signal,
    };

    const response = await fetch(
        nlp_server_address + "/ml-api/citation-formatting-service/v1.0",
        requestOptions
    );
    const response_data = await response.json();
    const response_data_response = await response_data["response"];
    clearTimeout(timeout_id);

    return response_data_response;
}

// function get_all_element_keys(paperInfoList,paper_offset,num_papers_per_page){
//      const filtered_paper_info_list =  paperInfoList.map( (item, idx)=>{ return {item:item, idx:idx} } ).filter(
//           (item, idx)=>{
//               return (idx >=paper_offset && idx< paper_offset+num_papers_per_page && idx < paperInfoList.length);
//           });
//      let key_list = [];

//      for (let paper_i=0; paper_i<filtered_paper_info_list.length; paper_i++){
//         const paper_idx = filtered_paper_info_list[paper_i].idx;
//         const paper_info = filtered_paper_info_list[paper_i].item;
//         // extracted sentences
//         const highlights_info = paper_info.highlights_info;
//         for (let highlight_i = 0; highlight_i<highlights_info.length; highlight_i ++){
//             key_list.push(
//                 JSON.stringify( { "paper_idx":paper_idx.toString(),
//                                   "field_name":"highlights",
//                                   "sentence_id":highlight_i.toString(),
//                                 } )
//              );
//         }

//         // abstract and fullbody
//         const field_names = [ "abstract", "fullbody" ];
//         for ( let field_i = 0; field_i< field_names.length;field_i++ ){
//           const field_name = field_names[field_i];
//           const sections = (field_name==="abstract")?(paper_info.content_info.Content??{}).Abstract_Parsed??[] :
//                                                     (paper_info.content_info.Content??{}).Fullbody_Parsed??[] ;

//           for (let sec_i = 0; sec_i<sections.length; sec_i ++){
//             const section = sections[sec_i];
//             const section_id = section.section_id;
//             const section_text = section.section_text;
//             for ( let para_i = 0; para_i<section_text.length; para_i++){
//                 const paragraph = section_text[para_i];
//                 const paragraph_id = paragraph.paragraph_id;
//                 const paragraph_text = paragraph.paragraph_text;
//                 for ( let sen_i = 0; sen_i<paragraph_text.length; sen_i ++){
//                     const sentence = paragraph_text[sen_i];
//                     const sentence_id = sentence.sentence_id;
//                     key_list.push(
//                           JSON.stringify(
//                               {
//                                   "paper_idx":paper_idx.toString(),
//                                   "field_name":field_name.toString(),
//                                   "section_id":section_id.toString(),
//                                   "paragraph_id":paragraph_id.toString(),
//                                   "sentence_id":sentence_id.toString()
//                               })
//                           );
//                 }

//             }
//           }

//         }

//         //Reference
//         const references = paper_info.content_info.Reference??[];
//         for (let ref_i = 0; ref_i < references.length; ref_i++ ){
//             key_list.push(
//                           JSON.stringify(
//                               {
//                                   "paper_idx":paper_idx.toString(),
//                                   "field_name":"references",
//                                   "reference_id":ref_i.toString()
//                               })
//                           );
//         }

//      }

//      return key_list;
//   }
