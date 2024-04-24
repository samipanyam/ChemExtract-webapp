
import { goto } from '$app/navigation';

export let data = [];





export async function PDFprocessor(files: FileList) {
  if (files.length > 0) {
    var  LoadingSign= document.getElementsByClassName("center")[0];
    var button = document.getElementsByClassName("button")[0];
    var button2 = document.getElementsByClassName("button")[1];
    var button3 = document.getElementsByClassName("button")[2];
    var list = document.getElementsByClassName("list")[0];


    button.style.display = (button.style.display === 'none' || button.style.display === '') ? 'none' : 'center';
    button2.style.display = (button2.style.display === 'none' || button2.style.display === '') ? 'none' : 'center';

    LoadingSign.style.display = (LoadingSign.style.display === 'none' || LoadingSign.style.display === '') ? 'flex' : 'none';
    list.style.display = (list.style.display === 'none' || list.style.display === '') ? 'none' : 'flex';


   var list_of_molecules = await postPDFs(files);
   console.log(list_of_molecules["data"]);
   
    
 
    LoadingSign.style.display = (LoadingSign.style.display === 'none' || LoadingSign.style.display === '') ? 'flex' : 'none';
    button3.style.display =  'center';

    
    goto('/list')
  } else {
    alert('Please select a PDF to process');
  }
}



export async function postPDFs(files: FileList) {
  const formData = new FormData();
 
  


  for (let i = 0; i < files.length; i++) {
    formData.append('files', files[i]);
    console.log(files[i]);
    
  }


  try {
    const response = await fetch('http://127.0.0.1:5000/extract', {
     

      method: 'POST',
      body: formData,
      credentials: 'include',
      
    });

    const data = await response.json();
    console.log(data);
    return data
  } catch (error) {
    console.error('Error sending request:', error);
  }
}

export async function getSmilesData() {
  const response = await fetch('http://127.0.0.1:5000/load_smiles_data' , {
    method: 'GET',
    credentials: 'include',
  });
  

  const data = await response.json(); // Await the JSON parsing
  return data;
}

export async function getPubchemData() {
  const response = await fetch('http://127.0.0.1:5000/load_pubchempy_data' , {

    method: 'GET',
    credentials: 'include',
  });
  const data = await response.json(); // Await the JSON parsing
  return data;
}

interface ChemicalInfo {
  [key: string]: string;

}

export async function sendData(chemical_info: ChemicalInfo) {
  // Function logic here
  const response = await fetch('http://127.0.0.1:5000/get_pubchempy_data', {

    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(chemical_info)
  });

  goto('/info')
  
}
