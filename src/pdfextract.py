import os
import fitz
import cv2
import numpy as np
import torch
import re
import asyncio
import pubchempy as pcp
from pdf2image import convert_from_path
from molscribe import MolScribe
from decimer_segmentation import segment_chemical_structures, get_mrcnn_results
from transformers import AutoTokenizer, BertForTokenClassification
from collections import defaultdict
from  huggingface_hub import hf_hub_download
import json
from more_itertools import unique_everseen
import time
import shutil
import boto3



def delete_s3_folder(bucket_name, folder_prefix):
    try:
        s3 = boto3.client('s3')
        objects_to_delete = []

        # List objects in the specified folder
        paginator = s3.get_paginator('list_objects_v2')
        for result in paginator.paginate(Bucket=bucket_name, Prefix=folder_prefix):
            if 'Contents' in result:
                for obj in result['Contents']:
                    objects_to_delete.append({'Key': obj['Key']})

        # Delete objects
        if objects_to_delete:
            s3.delete_objects(Bucket=bucket_name, Delete={'Objects': objects_to_delete})
    except Exception as e:
        print(f"Error deleting S3 folder: {e}")



def upload_folder_to_s3(local_folder_path, bucket_name, s3_folder_path=''):
    s3 = boto3.client('s3')

    for root, dirs, files in os.walk(local_folder_path):
        for file in files:
            local_file_path = os.path.join(root, file)
            s3_file_path = os.path.join(s3_folder_path, os.path.relpath(local_file_path, local_folder_path))
            s3.upload_file(local_file_path, bucket_name,local_folder_path +"/"+s3_file_path)
async def fetch_from_pcp(keyword, type, output):
    try:
        compound = pcp.get_compounds(keyword, type)[0]
        return compound.canonical_smiles
    except pcp.PubChemHTTPError as e:
        if hasattr(e, 'args') and len(e.args) > 0:
            error_name = e.args[0]
            if error_name == 'PUGREST.ServerBusy':
                print(f"Rate limit exceeded. Retrying after {e.headers['Retry-After']} seconds...")
                retry_after = int(e.headers['Retry-After'])
                await asyncio.sleep(retry_after)
                return await fetch_from_pcp(keyword, type, output)
    except (IndexError, KeyError):
        return None
    except Exception as e:
        print(f"Error fetching compound smiles: {e}")
        return None


def extract_text_from_pdf(file_path: str, page_number: int = 0) -> str:
    doc = fitz.open(file_path)
    page = doc.load_page(page_number)
    text = page.get_text("text")
    return text


def extract_text_from_pdf_all_pages(file_path: str) -> list:
    doc = fitz.open(file_path)
    text_pages = []

    for page_number in range(len(doc)):
        page = doc.load_page(page_number)
        text = page.get_text("text")
        text_pages.append(text)

    return text_pages


def split_text(text: str, max_length: int) -> list:
    # Split the text into chunks of maximum length
    chunks = [text[i:i + max_length] for i in range(0, len(text), max_length)]
    return chunks


class StructureExtractor:
    def __init__(self, filename: str, pathtosave: str = None):
        self.filename = filename
        self.filename_without_extension = os.path.splitext(self.filename)[0]
        self.pathtosave = pathtosave
        ckpt_path =  hf_hub_download('yujieq/MolScribe', 'swin_base_char_aux_1m.pth')
        self.model = MolScribe(ckpt_path)
        self.pngs = []
        self.segments = []
        self.smiles = []

    def PDFtoPNG(self):
        if not self.pngs:
            pngs = convert_from_path(self.filename)
            if self.pathtosave:
                folder_path = self.pathtosave + '/' + 'Page_PNGS'
            else:
                folder_path = 'Page_PNGS'
            
            if not os.path.exists(folder_path):
                os.makedirs(folder_path)

            for index, page in enumerate(pngs):
                extracted_page = np.array(page)
                png_path = f'{folder_path}/{os.path.basename(self.filename_without_extension)}_{index}.png'
                cv2.imwrite(png_path, extracted_page)
                self.pngs.append(extracted_page)

        return self.pngs

    async def segment(self):
        try:
            if not self.segments:
                if self.pathtosave:
                    folder_path = self.pathtosave + '/' + 'segments'
                else:
                    folder_path = 'segments'

                if not os.path.exists(folder_path):
                    os.makedirs(folder_path)

                if not self.pngs:
                    self.PDFtoPNG()

                for index, img in enumerate(self.pngs):
                    start = time.time()
                    minisegments = segment_chemical_structures(img, expand=False)
                    print(f"making segments took {time.time() - start} seconds")
                    _, bounding_boxes, _ = get_mrcnn_results(img)
                    averages = [str(row[0]) for row in bounding_boxes] + [str(row[1]) for row in bounding_boxes]
                    Widths = [str(row[2]-row[0]) for row in bounding_boxes]
                    Heights = [str(row[3]-row[1]) for row in bounding_boxes]
                    grouped_averages = [[averages[i], averages[i + len(bounding_boxes)]] for i in range(len(bounding_boxes))]
                
                    minis = []
                    for idx, minisegment in enumerate(minisegments):
                        minisegment_array = np.array(minisegment)
                        minisegment = minisegment_array[:, :, :3]
                    
                        minisegment = [minisegment, idx, grouped_averages[idx], Widths[idx], Heights[idx], os.path.basename(self.filename_without_extension)]
                        minis.append(minisegment)
                        
                        cv2.imwrite(f'{folder_path}/{os.path.basename(self.filename_without_extension)}_{idx}.png', minisegment[0])


                    self.segments.extend(minis)

            return self.segments
        except Exception as e:
            print(e)
            return None

    async def toSMILES(self):
            if not self.smiles:
                output = []
                if self.pathtosave:
                    folder_path = self.pathtosave + '/' + 'SMILES'
                else:
                    folder_path = 'SMILES'
                if not os.path.exists(folder_path):
                    os.makedirs(folder_path)
                
                subfolder = 'PDF_SMILES'

                if not os.path.exists(f'{folder_path}/{subfolder}'):
                    os.makedirs(f'{folder_path}/{subfolder}')
                
                smiles_txt_path = f'{folder_path}/{subfolder}/{os.path.basename(self.filename_without_extension)}.json'
                
                if os.path.exists(smiles_txt_path):
                
                    return json.load(open(smiles_txt_path, 'r'))
                
                
                if not self.segments:
                    start = time.time()
                    await self.segment()
                    print(f"Segmentation took {time.time() - start} seconds")

                
                start = time.time()
                for i, img in enumerate(self.segments):
                    
                    SMILES = self.model.predict_image(img[0])['smiles']
                    
                    try:
                        chemical = pcp.get_compounds(SMILES, 'smiles')[0]
                        cid = chemical.cid
                        keyword = chemical.iupac_name
                        
                    except pcp.BadRequestError:
                        cid = None
                        keyword = None
                          
                    to_add = {
                        'SMILES': SMILES,
                        'page': img[1],
                        'cid': cid,
                        'keyword': keyword,
                        'X': img[2][0],
                        'Y': img[2][1],
                        'Height': img[3],
                        'Width': img[4],
                        'article': img[5],
                        'image': f'segments/{os.path.basename(self.filename_without_extension)}_{i}.png'
                    }
                    output.append(to_add)
                    
                self.smiles = output
                end = time.time()
                print(f"SMILES extraction took {end - start} seconds")
                with open(smiles_txt_path, 'w') as f:
                    json.dump(self.smiles, f)
                

            return self.smiles
        # except Exception as e:
        #     print(e)
        #     return None


class TextExtractor:
    tokenizer = AutoTokenizer.from_pretrained('pruas/BENT-PubMedBERT-NER-Chemical')
    model = BertForTokenClassification.from_pretrained('pruas/BENT-PubMedBERT-NER-Chemical')

    def __init__(self, filename: str, pathtosave: str = None):
        self.filename = filename
        self.pathtosave = pathtosave
        self.filename_without_extension = os.path.splitext(self.filename)[0]
        self.keywords = None
        self.text = None
        self.total_text = None
        self.preprocessed_keywords = []
    def find_all_occurrences(self,input_string, substring):
        try:
            occurrences = []
            start_index = 0

            while True:
                index = input_string.find(substring, start_index)
                if index == -1:
                    break
                occurrences.append(index)
                start_index = index + 1
            return occurrences
        except Exception as e:
            print(e)
        


    def extract(self) -> list:
        if self.text is None:
            self.text = extract_text_from_pdf_all_pages(self.filename)
            delimiter = ' '
            self.total_text = delimiter.join(self.text)

        return self.text

    async def process_page(self, page_text):
        
        start = time.time()
        # Asynchronously process a single page's keywords
        all_keywords_with_page_number_and_index = defaultdict(list)
        split_page = split_text(page_text, 800)
        for text_splice in split_page:
            inputs = self.tokenizer.encode_plus(text_splice, return_tensors="pt", add_special_tokens=True)
            outputs = self.model(inputs.input_ids, attention_mask=inputs.attention_mask)
            predicted_labels = torch.argmax(outputs.logits, dim=2)[0]
            predicted_tokens = self.tokenizer.convert_ids_to_tokens(inputs.input_ids[0])
            keywords = []
            for token, label_idx in zip(predicted_tokens, predicted_labels):
                    if label_idx != 0:
                        keywords.append(token)
            self.preprocessed_keywords.append(keywords) 
            # combined_tokens = []
            # for token in keywords:
            #     if token.startswith("##") and combined_tokens:
            #         combined_tokens[-1] += token[2:]
            #     else:
            #         combined_tokens.append(token)
            
            words =text_splice.split()
            
            new_keywords = []
            for token in keywords:
                if token.startswith("##"):
                    partial_word = token[2:]
                    
                    if len(partial_word) > 2 and partial_word.isnumeric() == False:
                       
                       matches = filter(lambda word: partial_word in word, words)
                       new_keywords.extend(list(matches))
                else:
                    new_keywords.append(token)

                   
            keywords = new_keywords
            
           
            for token in keywords:
                
                    keyword = token.strip()
                  
                    if keyword in self.total_text and len(keyword)>3:
                        
                       
                        
                        start_index = self.find_all_occurrences(self.total_text, keyword)
                        end_index = [index + len(keyword) for index in start_index]
                        indeces = list(zip(start_index, end_index))


                        all_keywords_with_page_number_and_index[keyword].append((
                            keyword,
                            self.text.index(page_text),
                            indeces
                            
                        ))

        flattened_keywords = [item for sublist in all_keywords_with_page_number_and_index.values() for item in sublist]
        
        unique_keywords = []
        seen_keywords = set()

        for entry in flattened_keywords:
            
            if entry[0] not in seen_keywords:
                unique_keywords.append({
                    "keyword": entry[0],
                    "page": entry[1],
                    "index": entry[2]
                })
                seen_keywords.add(entry[0])
        end = time.time()
        print(f"Page processing took {end - start} seconds")
        return unique_keywords





    async def getKeywords(self):
        start = time.time()
        if self.keywords is None:
            text = self.extract()
            delimiter = ' '
            self.total_text = delimiter.join(text)

            # Asynchronously process keywords for each page
            page_tasks = [self.process_page(page) for page in text]
            all_keywords = await asyncio.gather(*page_tasks)

            # Combine keywords from all pages
            self.keywords = [keyword for page_keywords in all_keywords for keyword in page_keywords]
        
        end = time.time()
        print(f"Keyword extraction took {end - start} seconds")
        return self.keywords

    async def toSMILES(self) -> list:
        start = time.time()
        if self.pathtosave:
            folder_path = self.pathtosave + '/' + 'SMILES'
        else:
            folder_path = 'SMILES'
        
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
        subfolder = 'TEXT_SMILES'
        if not os.path.exists(f'{folder_path}/{subfolder}'):
            os.makedirs(f'{folder_path}/{subfolder}')
        if os.path.exists(f'{folder_path}/{subfolder}/{os.path.basename(self.filename_without_extension)}.json'):
           
           return json.loads(open(f'{folder_path}/{subfolder}/{os.path.basename(self.filename_without_extension)}.json', 'r').read())
        if self.keywords is None:
           await self.getKeywords()
        

        
            

        async def fetch_compound(keyword):
            start = time.time()
            try:
                compound = pcp.get_compounds(keyword["keyword"], 'name')[0]
                end = time.time()
                print(f"Fetching compound smiles for {keyword['keyword']} took {end - start} seconds")
                return compound
            except pcp.PubChemHTTPError as e:
                if hasattr(e, 'args') and len(e.args) > 0:
                    error_name = e.args[0]
                    if error_name == 'PUGREST.ServerBusy':
                        print(f"Rate limit exceeded. Retrying after {e.headers['Retry-After']} seconds...")
                        retry_after = 2
                        await asyncio.sleep(retry_after)
                        return await fetch_compound(keyword)
            except (IndexError, KeyError):
                return None
            except Exception as e:
                print(f"Error fetching compound smiles: {e}")
                return None

        tasks = [fetch_compound(keyword) for keyword in self.keywords]
        start = time.time()
        filtered_compounds= await asyncio.gather(*tasks)
        end = time.time()
        print(f"Fetching compound smiles took {end - start} seconds")
        filtered_SMILES = [compound.canonical_smiles if compound is not None else None for compound in filtered_compounds]

        tor = []
        for compound in filtered_compounds:
            SMILES =  compound.canonical_smiles if compound is not None else None
            cid = compound.cid if compound is not None else None
            tor.append({
                "keyword": self.keywords[filtered_SMILES.index(SMILES)]["keyword"],
                "SMILES": SMILES,
                "cid": cid,
                "page": self.keywords[filtered_SMILES.index(SMILES)]["page"],
                "index": self.keywords[filtered_SMILES.index(SMILES)]["index"]
            })

        filtered_keywords = [keyword for keyword in tor if keyword["SMILES"] is not None]

        with open(f'{folder_path}/{subfolder}/{os.path.basename(self.filename_without_extension)}.json', 'w') as f:
            json.dump(filtered_keywords, f)

        end = time.time()
        print(f"SMILES extraction took {end - start} seconds")
        return filtered_keywords


class BatchExtractor:
    SMILES = None
    pdf_list = []
    text_list = []
    pathtosave = None
    def __init__(self, path: str, pathtosave: str = None):
            
            print(os.path.isdir(path))
            if os.path.isdir(path):
                self.pdf_list = []
                self.text_list =[]
            
                self.pathtosave = pathtosave

                files = os.listdir(path)
                for filename in files:
                    if filename.endswith(".pdf"):
                        print(f'{path}/{filename}')
                        self.pdf_list.append(StructureExtractor(f'{path}/{filename}', pathtosave))
                        self.text_list.append(TextExtractor(f'{path}/{filename}', pathtosave))
            elif os.path.isfile(path):
                if path.endswith(".pdf"):
                    self.pdf_list = [StructureExtractor(path, pathtosave)]
                    self.text_list = [TextExtractor(path, pathtosave)]
           
            print("hi")

    async def toSMILES(self):
        try:
            tor = {}
            tor["PDF_SMILES"] = []
            tor["Text_SMILES"] = []

            for extractor in self.pdf_list:
                pdf_smiles = await extractor.toSMILES()
                tor["PDF_SMILES"].append(pdf_smiles)  # Await the asynchronous call

            for extractor in self.text_list:
                text_smiles = await extractor.toSMILES()
                tor["Text_SMILES"].append(text_smiles)

            self.SMILES = tor
            return tor
        except Exception as e:
            print(e)
            return None



    async def combine(self):
        try:
            if self.SMILES is None:
                await self.toSMILES()
            
            folder_path = 'SMILES'
            subfolder = 'COMBINED_SMILES'
            print("hi")
            if not os.path.exists(f'{folder_path}/{subfolder}'):
                os.makedirs(f'{self.pathtosave}/{folder_path}/{subfolder}')
            print("hi")
            if os.path.exists(f'{self.pathtosave}/{folder_path}/{subfolder}/OUTPUT.json'):
                return json.loads(open(f'{self.pathtosave}/{folder_path}/{subfolder}/OUTPUT.json', 'r').read())

            pdf_canonical_smiles = []
            text_canonical_smiles = []
            pdf_canonical_smiles = [{"SMILES": keyword["SMILES"],"cid": keyword["cid"],"page": keyword["page"],"keyword": keyword["keyword"],"X": keyword["X"],"Y": keyword["Y"],"Height" :keyword["Height"], "Width" : keyword["Width"]  , "origin": self.pdf_list[self.SMILES["PDF_SMILES"].index(pdf_smiles)].filename_without_extension,"image": keyword["image"]} for pdf_smiles in self.SMILES["PDF_SMILES"] for keyword in pdf_smiles]

            text_canonical_smiles = [{ "SMILES": keyword["SMILES"],"keyword": keyword["keyword"],"cid": keyword["cid"],"page": keyword["page"],"index": keyword["index"],"origin": self.text_list[self.SMILES["Text_SMILES"].index(text_smiles)].filename_without_extension} for text_smiles in self.SMILES["Text_SMILES"] for keyword in text_smiles]
            final_list = []
            pdf_smiles_map = {entry["SMILES"]: entry for entry in pdf_canonical_smiles if entry["SMILES"] is not None}
            print(":3")
            for text_smiles in text_canonical_smiles:
                if text_smiles["SMILES"] in pdf_smiles_map:
                    pdf_entry = pdf_smiles_map[text_smiles["SMILES"]]
                    final_entry = {
                        "SMILES": pdf_entry["SMILES"],
                        "cid": pdf_entry["cid"],
                        "page": pdf_entry["page"],
                        "keyword": text_smiles["keyword"],
                        "X": pdf_entry["X"],
                        "Y": pdf_entry["Y"],
                        "Height": pdf_entry["Height"],
                        "Width": pdf_entry["Width"],
                        "origin": pdf_entry["origin"],
                        "image": self.pathtosave + "/" + pdf_entry["image"] if self.pathtosave else pdf_entry["image"]
                    }
                    if "index" in text_smiles:
                        final_entry["index"] = text_smiles["index"]
                    final_list.append(final_entry)

                

            
                # Create a list comprehension to filter out text_smiles not present in final_list
            text_canonical_smiles = [text_smiles for text_smiles in text_canonical_smiles if text_smiles["SMILES"] not in [smiles["SMILES"] for smiles in final_list]]
            print(":3")
            for pdf_smiles in pdf_canonical_smiles:
                if  self.pathtosave:
                    final_list.append({
                        "SMILES": pdf_smiles["SMILES"],
                        "cid": pdf_smiles["cid"],
                        "page": pdf_smiles["page"],
                        "keyword": pdf_smiles["keyword"],
                        "X": pdf_smiles["X"],
                        "Y": pdf_smiles["Y"],
                        "Height": pdf_smiles["Height"],
                        "Width": pdf_smiles["Width"],
                        "origin": pdf_smiles["origin"],
                        "image": self.pathtosave + "/"+ pdf_smiles["image"],
                    })
                else:
                    final_list.append({
                        "SMILES": pdf_smiles["SMILES"],
                        "cid": pdf_smiles["cid"],
                        "page": pdf_smiles["page"],
                        "keyword": pdf_smiles["keyword"],
                        "X": pdf_smiles["X"],
                        "Y": pdf_smiles["Y"],
                        "Height": pdf_smiles["Height"],
                        "Width": pdf_smiles["Width"],
                        "origin": pdf_smiles["origin"],
                        "image": pdf_smiles["image"]
                    })

            
            
            for text_smiles in text_canonical_smiles:
                final_list.append({
                    "SMILES": text_smiles["SMILES"],
                    "cid": text_smiles["cid"],
                    "page": text_smiles["page"],
                    "keyword": text_smiles["keyword"],
                    "index": text_smiles["index"],
                    "origin": text_smiles["origin"]
                })
            
            final_list = [item for item in final_list if item['cid'] is not None]
            print(":3")

            sorted_data_by_cid = sorted(final_list, key=lambda x: x.get('cid', float('-inf')), reverse=True)

            print(":3")
            
            try: 
                sorted_data_by_cid = tuple(sorted_data_by_cid)
            except Exception as e:
                print(e)

            try: 
                sorted_data_by_cid = list(unique_everseen(sorted_data_by_cid))
                print(sorted_data_by_cid)
            except Exception as e:
                print(e)
            
            with open(f'{self.pathtosave}/{folder_path}/{subfolder}/OUTPUT.json', 'w') as f:
                json.dump(final_list, f)

            return sorted_data_by_cid
        except Exception as e:
            print(e)
            return None
def highlightPDF(userfolder, keyword):
    for filename in os.listdir(userfolder):
        print("hi")
        if filename.endswith('.pdf'):  # Check if the file is a PDF
            pdf_path = os.path.join(userfolder, filename)
            try:
                pdf_document = fitz.open(pdf_path)
                for page_number in range(len(pdf_document)):
                    page = pdf_document.load_page(page_number)
                    text_instances = page.search_for(keyword)
                    try:
                        for inst in text_instances:
                            highlight = page.add_highlight_annot(inst)

                    except ValueError as e:
                        print(f"Error adding highlight annotation to page {page_number + 1} of {filename}: {e}")
                pdf_document.save(os.path.join(userfolder, "highlighted_" + filename))
                pdf_document.close()
            except Exception as e:
                print(f"Error processing PDF file {filename}: {e}")
def highlightPDFImage(userfolder, X,Y,Height,Width,page):
    for filename in os.listdir(userfolder):
        print("hi")
        if filename.endswith('.pdf'):  # Check if the file is a PDF
            pdf_path = os.path.join(userfolder, filename)
            try:
                pdf_document = fitz.open(pdf_path)
                

                pdf_page = pdf_document.load_page(int(page))
                try:
                   
                    highlight = pdf_page.add_rect_annot([X,Y,X+Width,Y+Height])

                except ValueError as e:
                    print(f"Error adding highlight annotation to page { page + 1} of {filename}: {e}")
                pdf_document.save(os.path.join(userfolder, "highlighted_" + filename))
                pdf_document.close()
            except Exception as e:
                print(f"Error processing PDF file {filename}: {e}")

                        
            
                        







