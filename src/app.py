from flask import Flask, jsonify, request
from flask_cors import CORS
from pdfextract import BatchExtractor, highlightPDF, highlightPDFImage, upload_folder_to_s3
import asyncio
import os
import shutil
import uuid
import pubchempy as pcp
import json
import boto3

app = Flask(__name__)
CORS(app, supports_credentials=True)

@app.route('/extract', methods=['POST', 'GET'])
def extract_data():
    try:
        # Generate a unique folder name for each user
        global user_folder
        global bucket_name


        user_folder = 'temp_files_' + str(uuid.uuid4())
        bucket_name = 'chemextract'
        

        files = request.files.getlist('files')
        os.environ["TOKENIZERS_PARALLELISM"] = "false"
        
        # Save the files to the user's folder
        if not os.path.exists(user_folder):
            os.makedirs(user_folder)
        
        file_paths = []
        for idx, file in enumerate(files):
            file_path = os.path.join(user_folder, f'file_{idx}.pdf')
            file.save(file_path)
            file_paths.append(file_path)

        # Initialize BatchExtractor
        extractor = BatchExtractor(user_folder, user_folder)

        # Extract SMILES data
        smiles_data = asyncio.run(extractor.combine())

        # Save the SMILES data to a file
        with open(os.path.join(user_folder, 'smiles_data.json'), 'w') as json_file:
            json.dump(smiles_data, json_file)
        
        # Upload the user's folder to S3

        upload_folder_to_s3(user_folder, bucket_name)
        return jsonify({
            'message': 'Success',
            'data': smiles_data,
            'folder': user_folder
        }), 200

    except Exception as e:
        shutil.rmtree(user_folder)
        return jsonify({
            'message': f'Error: {str(e)}'

        }), 500
    
@app.route('/load_smiles_data')
def get_smiles_data():
    try:
        # Retrieve the user's folder based on request parameters or session data
         # Adjust this according to your authentication/session mechanism
        with open(os.path.join(user_folder, 'smiles_data.json'), 'r') as json_file:
            smiles_data = json.load(json_file)
        upload_folder_to_s3(user_folder, bucket_name)

        return jsonify(smiles_data), 200
    
    except FileNotFoundError:
        return jsonify({'error': 'SMILES data not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500





@app.route('/get_pubchempy_data', methods=['POST'])
def get_pubchempy_data():
    filename = os.path.join(user_folder, 'pubchempy_data.json')
    chemical_data = request.get_json()
    if "image" in chemical_data:
        highlightPDFImage(user_folder, chemical_data.get("X", ''), chemical_data.get("Y", ''), chemical_data.get("Height", ""), chemical_data.get("Width", ""), chemical_data.get("page", ""))
    else:
        highlightPDF(user_folder, chemical_data.get("keyword", "") )
    
    print(chemical_data)
    if 'cid' not in chemical_data:
        return jsonify({'error': 'CID not provided'}), 400

    cid = chemical_data['cid']
    compound = pcp.Compound.from_cid(cid)

    if 'image' in chemical_data:
        properties = {
            "keyword": chemical_data.get("keyword", ""),
            "CID": cid,
            "Compound Name": compound.iupac_name,
            "Molecular Formula": compound.molecular_formula,
            "Molecular Weight": compound.molecular_weight,
            "Canonical SMILES": compound.canonical_smiles,
            "Isomeric SMILES": compound.isomeric_smiles,
            "XLogP": compound.xlogp,
            "Exact Mass": compound.exact_mass,
            "Charge": compound.charge,
            "Complexity": compound.complexity,
            "Image": chemical_data["image"],
            "page": chemical_data["page"],

            "origin": chemical_data["origin"]
        }
    else:
        properties = {
            "keyword": chemical_data.get("keyword", ""),
            "CID": cid,
            "Compound Name": compound.iupac_name,
            "Molecular Formula": compound.molecular_formula,
            "Molecular Weight": compound.molecular_weight,
            "Canonical SMILES": compound.canonical_smiles,
            "Isomeric SMILES": compound.isomeric_smiles,
            "XLogP": compound.xlogp,
            "Exact Mass": compound.exact_mass,
            "Charge": compound.charge,
            "Complexity": compound.complexity,
            "origin": chemical_data["origin"]
        }

    with open(filename, 'w') as json_file:
        json.dump(properties, json_file)
    print(properties)

    
    upload_folder_to_s3(user_folder, bucket_name)
    return jsonify(properties), 200


@app.route('/load_pubchempy_data', methods=['GET'])
def load_pubchempy_data():
    try:
        filename = os.path.join(user_folder, 'pubchempy_data.json')
        with open(filename, 'r') as json_file:
            data = json.load(json_file)

        upload_folder_to_s3(user_folder, bucket_name)
        return jsonify(data), 200
    except FileNotFoundError:
        return jsonify({'error': 'PubChemPy data not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
       








if __name__ == '__main__':
    app.run(debug=True)
