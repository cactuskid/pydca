from pydca.sequence_backmapper.sequence_backmapper import SequenceBackmapper
from pydca.fasta_reader.fasta_reader import get_alignment_from_fasta_file
import ctypes 
import logging
import os
import glob 
import numpy as np

"""Python wrapper for psuedolikelihood maximization direct coupling analysis (plmDCA).
The gradient decent algorithm is implemented using c++ backend.

Author: Mehari B. Zerihun
"""

logger = logging.getLogger(__name__)


class PlmDCAException(Exception):
    """Implements exceptions related to PlmDCA computation
    """

class PlmDCA:
    """Wraps  the c++ implementation of plmDCA.

    Attributes
    ----------
        plmdca_so : str 
            Path to the plmDCA shared object created from the C++ source code
    """
    plmdca_so_paths  = glob.glob(
        os.path.join(os.path.dirname(__file__), '_plmdcaBackend*')
    )
    logger.info('\n\tplmdca backend path: {}'.format(plmdca_so_paths))
    try:
        plmdca_lib_path = plmdca_so_paths[0]
    except IndexError:
        logger.error('\n\tUnable to find plmdca dynamic library path.' 
            '\nAre you running  pydca as a module before installation?'
            '\nIn this case you need to build the plmdca shared object.'
        )
        raise 


    def __init__(self, biomolecule, msa_file, seqid=None, lambda_h=None, 
            lambda_J=None, max_iteration=None, num_threads=None, verbose=False):
        """Initilizes plmdca instances
        """

        self.__biomolecule = biomolecule.strip().upper()
        if self.__biomolecule not in ('PROTEIN', 'RNA'):
            logger.error('\n\tInvalid biomolecule type {}'.format(self.__biomolecule))
            raise PlmDCAException
        self.__msa_file = msa_file
        self.__biomolecule_int = 1 if self.__biomolecule == 'PROTEIN' else 2
        self.__num_site_states = 21 if self.__biomolecule== 'PROTEIN' else 5
        self.__num_seqs, self.__seqs_len = self._get_num_and_len_of_seqs()
        self.__seqid = 0.8 if seqid is None else seqid 
        if self.__seqid <= 0 or self.__seqid > 1.0: 
            logger.error('\n\t{} is an invalid value of sequences identity (seqid) parameter'.format(self.__seqid))
            raise PlmDCAException 
        self.__lambda_h= 1.0 if lambda_h is None else lambda_h
        if self.__lambda_h < 0 :
            logger.error('\n\tlambda_h must be a positive number. You passed lambda_h={}'.format(self.__lambda_h))
            raise PlmDCAException  
        self.__lambda_J=  0.2*(self.__seqs_len - 1) if lambda_J is None else lambda_J
        if self.__lambda_J < 0: 
            logger.error('\n\tlambda_J must be a positive number. You passed lambda_J={}'.format(self.__lambda_J))
            raise PlmDCAException
        self.__max_iteration = max_iteration if max_iteration is not None else 100
        self.__num_threads = 1 if num_threads is None else num_threads
        self.__verbose = True if verbose else False  
        # plmdcaBackend interface
        # extern "C" float* plmdcaBackend(unsigned short const biomolecule, unsigned short const num_site_states, 
        # const char* msa_file, unsigned int const seqs_len, float const seqid, float const lambda_h, 
        # float const lambda_J, unsigned int const max_iteration)
        self.__plmdca = ctypes.CDLL(self.plmdca_lib_path)
        self.__plmdcaBackend = self.__plmdca.plmdcaBackend 
        self.__plmdcaBackend.argtypes = (ctypes.c_ushort, ctypes.c_ushort, ctypes.c_char_p, ctypes.c_uint, 
            ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_uint, ctypes.c_uint, ctypes.c_bool)
        data_size = (self.__seqs_len * (self.__seqs_len - 1) * (self.__num_site_states ** 2))/2 + self.__seqs_len * self.__num_site_states
        self.__data_size = int(data_size) 
        self.__plmdcaBackend.restype = ctypes.POINTER(ctypes.c_float * self.__data_size)
        #extern "C" void freeFieldsAndCouplings(float*& fields_and_couplings)
        self.freeFieldsAndCouplings = self.__plmdca.freeFieldsAndCouplings
        #self.freeFieldsAndCouplings.argtypes = (ctypes.POINTER(ctypes.c_float),) 
        self.freeFieldsAndCouplings.restype = None 
        log_message="""Created plmDCA instance with:
            biomolecule: {}
            MSA sequence length: {}
            total number of (unweighted) sequences: {}
            sequence identity: {}
            lambda_h: {}
            lambda_J: {}
            gradient decent iterations: {}
            number of threads: {}
        """.format(self.__biomolecule, self.__seqs_len, self.__num_seqs, 
            self.__seqid, self.__lambda_h, self.__lambda_J, self.__max_iteration,
            self.__num_threads,
        )
        logger.info(log_message)
        return None


    @property
    def biomolecule(self):
        """
        """
        return self.__biomolecule


    @property
    def sequence_identity(self):
        """
        """
        return self.__seqid


    @property
    def lambda_h(self):
        """
        """
        return self.__lambda_h
    

    @property
    def lambda_J(self):
        """
        """
        return self.__lambda_J


    @property
    def max_iteration(self):
        """
        """
        return self.__max_iteration


    @property
    def sequences_len(self):
        """
        """
        return self.__seqs_len


    @property
    def num_sequences(self):
        """
        """
        return self.__num_seqs
    
    
    @property
    def effective_num_sequences(self):
        """
        """
        raise NotImplementedError
        
    

    
    

    def _get_num_and_len_of_seqs(self):
        """Obtains the length of sequences in MSA data.

        Parameters
        ----------
            self : PlmDCA 
                Instance of PlmDCA class
        
        Returns
        -------
            num_seqs, seqs_len: tuple  
                A tuple of the number and length of sequences as read from 
                the MSA file
        """
        msa_data = get_alignment_from_fasta_file(self.__msa_file)
        num_seqs = len(msa_data)
        seqs_len = len(msa_data[0])
        return num_seqs, seqs_len

    def map_index_couplings(self, i, j, a, b):
        """
        """
        q = self.__num_site_states
        L = self.__seqs_len
        site = int(((L *  (L - 1)/2) - (L - i) * ((L-i)-1)/2  + j  - i - 1) * q * q)
        k =  L * q + site + b + a * q
        return k
    
    
    def compute_params(self):
        """Compute fields and couplings using the C++ backend of plmDCA

        Parameters
        ----------
            self : PlmDCA
                An instance of PlmDCA class

        Returns
        -------
            fields_and_couplings : np.array
                A one-dimensional array of the fields and couplings
        """
        logger.info('\n\tComputing fields and coupling using gradient decent')
        h_J_ptr = self.__plmdcaBackend(
            self.__biomolecule_int, self.__num_site_states, self.__msa_file.encode('utf-8'), 
            self.__seqs_len,  self.__seqid, self.__lambda_h, self.__lambda_J, self.__max_iteration,
            self.__num_threads, self.__verbose
        )
        
        fields_and_couplings = np.zeros((self.__data_size,), dtype=np.float32)
        #fields_and_couplings = [c for c in h_J_ptr.contents]
        counter = 0
        for i, h_or_J in enumerate(h_J_ptr.contents):
            fields_and_couplings[i] = h_or_J
            counter += 1
        #Free fields and couplings data from PlmDCABackend
        h_J_ptr_casted = ctypes.cast(h_J_ptr, ctypes.POINTER(ctypes.c_void_p))
        self.freeFieldsAndCouplings(h_J_ptr_casted)

        #fields_and_couplings = np.array(fields_and_couplings, dtype=np.float32)
        
        try:
            assert fields_and_couplings.size == counter 
        except AssertionError:
            logger.error('\n\tData size mismatch from the plmDCA backend')
            raise
        else:
            logger.info('\n\tData size expected from plmDCA backend: {}'.format(self.__data_size))
            logger.info('\n\tData size obtained from plmDCA backend to Python: {}'.format(fields_and_couplings.size))

        return fields_and_couplings 


    def get_couplings_no_gap_state(self):
        """Extract the couplings from fields and couplings numpy array

        Parameters
        ----------
            self :   PlmDCA 
                An instanc of PlmDCA class
        Returns
        --------
            couplings : np.array
                A one-dimensional array of the couplings
        """
        fileds_and_couplings  = self.compute_params()
        couplings = list()
        for i in range(self.__seqs_len - 1):
            for j in range(i + 1, self.__seqs_len):
                for a in range(self.__num_site_states - 1):
                    for b in range(self.__num_site_states -1):
                        indx =  self.map_index_couplings(i, j , a, b)
                        couplings.append(fileds_and_couplings[indx])
        return np.array(couplings)


    def compute_sorted_FN(self):
        """Computes DCA scores using the Frobenius norm of the couplings. Note 
        that this score is not average product corrected.

        Parameters
        ----------
            self : PlmDCA
                An instance of PlmDCA class
            
        Returns
        --------
            dca_scores_not_apc : List of tuples of site pairs and DCA scores.
                The contents are sorted according to DCA score, in descending 
                order.
        """
        dca_scores_not_apc = list()
        L = self.__seqs_len
        q = self.__num_site_states
        couplings = self.get_couplings_no_gap_state()
        qm1 = q - 1
        logger.info('\n\tComputing non-APC sorted DCA score') 
        for i in range(self.__seqs_len -1):
            for j in range(i + 1, self.__seqs_len):
                start_indx = int(((L *  (L - 1)/2) - (L - i) * ((L-i)-1)/2  + j  - i - 1) * qm1 * qm1)
                end_indx = start_indx + qm1 * qm1
                couplings_ij = couplings[start_indx:end_indx]
                
                couplings_ij = np.reshape(couplings_ij, (qm1,qm1))
                avx = np.mean(couplings_ij, axis=1)
                avx = np.reshape(avx, (qm1, 1))
                avy = np.mean(couplings_ij, axis=0)
                avy = np.reshape(avy, (1, qm1))
                av = np.mean(couplings_ij)
                couplings_ij = couplings_ij -  avx - avy + av
                dca_score = np.sum(couplings_ij * couplings_ij)
                dca_score = np.sqrt(dca_score)
                data = ((i, j), dca_score)
                dca_scores_not_apc.append(data)
        dca_scores_not_apc = sorted(dca_scores_not_apc, key=lambda k : k[1], reverse=True)
        return dca_scores_not_apc


    def compute_sorted_FN_APC(self):
        """Performs average product correction (APC) of the Frobenius norm of the
        couplings for the plmDCA

        Parameters
        ---------
            self : PlmDCA
                An instance of PlmDCA class

        Returns 
        -------
            sorted_FN_APC : list of tuples
                A list of tuples of  site of pairs and APC DCA scores
        """ 
    
        # compute the average score of each site
        av_score_sites = list()
        N = self.__seqs_len
        scores_plmdca = self.compute_sorted_FN()
        logger.info('\n\tPerforming average product correction (APC) of FN  of DCA scores')
        for i in range(N):
            i_scores = [score for pair, score in scores_plmdca if i in pair]
            assert len(i_scores) == N - 1
            i_scores_sum = sum(i_scores)
            i_scores_ave = i_scores_sum/float(N - 1)
            av_score_sites.append(i_scores_ave)
        # compute average product corrected DI
        av_all_scores = sum(av_score_sites)/float(N)
        sorted_FN_APC = list()
        for pair, score in scores_plmdca:
            i, j = pair
            score_apc = score - av_score_sites[i] * (av_score_sites[j]/av_all_scores)
            sorted_FN_APC.append((pair, score_apc))
        # sort the scores as doing APC may have disrupted the ordering
        sorted_FN_APC = sorted(sorted_FN_APC, key = lambda k : k[1], reverse=True)
        return sorted_FN_APC
        


if __name__ == '__main__':
    """
    """
    